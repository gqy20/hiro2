from fastapi.testclient import TestClient

import apps.api.main as api_main
from apps.api.main import app


def test_health_contract() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_live_does_not_require_dependencies() -> None:
    response = TestClient(app).get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_returns_503_when_not_ready(monkeypatch) -> None:
    monkeypatch.setattr(
        api_main,
        "_health_status",
        lambda: {"status": "degraded", "postgres": "unavailable", "neo4j": "ok"},
    )
    response = TestClient(app).get("/health/ready")
    assert response.status_code == 503


def test_quality_overview_contract() -> None:
    response = TestClient(app).get("/api/v1/quality/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["task_total"] == 180
    assert "error_distribution" in body


def test_review_tasks_expose_human_readable_decision_context() -> None:
    body = TestClient(app).get("/api/v1/tasks/my").json()
    role_task = next(task for task in body["tasks"] if task["task_type"] == "role_level")
    assert role_task["system_output"]["question"] == "系统岗位映射是否准确？"
    assert role_task["system_output"]["predicted_position"]
    assert role_task["system_output"]["mapping_method"]

    domain_task = next(task for task in body["tasks"] if task["task_type"] == "evidence_audit")
    assert "domain_judgment" in domain_task["system_output"]
    assert domain_task["system_output"]["judgment_reason"]


def test_dashboard_overview_contract() -> None:
    response = TestClient(app).get("/api/v1/dashboard/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["focus"]["href"] == "/jobs"
    assert len(body["queue"]) == 3


def test_job_update_change_review_round_trip(isolated_review_log) -> None:
    """岗位更新逐条审核：提交留痕后能按草稿读取终态（隔离日志，不污染事实库）。"""
    client = TestClient(app)
    draft = "contract-draft"
    post = client.post(
        "/api/v1/jobs/default/updates/review",
        json={
            "draft": draft,
            "change_id": "chg-cap_03",
            "decision": "accepted",
            "note": "说明已编辑",
        },
    )
    assert post.status_code == 200 and post.json()["accepted"]
    # 后一条覆盖前一条（append-only 取终态）
    client.post(
        "/api/v1/jobs/default/updates/review",
        json={"draft": draft, "change_id": "chg-cap_03", "decision": "rejected", "note": ""},
    )
    body = client.get(f"/api/v1/jobs/default/updates/reviews?draft={draft}").json()
    assert body["reviews"]["chg-cap_03"]["decision"] == "rejected"
    # 其他草稿互不串读
    assert client.get("/api/v1/jobs/default/updates/reviews?draft=other").json()["reviews"] == {}


def test_job_update_changes_all_carry_evidence() -> None:
    """每条变化都有证据：空 evidence_ids 回退到观察窗内 JD 归因。"""
    body = TestClient(app).get("/api/v1/jobs/default/update?state=ready").json()
    assert body["changes"]
    for change in body["changes"]:
        assert change["evidence"], f"{change['title']} 缺少证据且回退归因失败"


def test_detected_changes_contract() -> None:
    """DetectedChanges 使用 snake_case VM 字段与合法 change_type。"""
    response = TestClient(app).get("/api/v1/jobs/detected-changes")
    assert response.status_code == 200
    body = response.json()
    assert body["changes_total"] == sum(len(job["changes"]) for job in body["jobs"])
    valid_types = {"add", "grow", "shrink", "remove"}
    for job in body["jobs"]:
        assert "position_id" in job and "base_jds" in job
        # job 是可读岗位名，解析失败才回退 position_id
        assert job["job"]
        for change in job["changes"]:
            assert change["change_type"] in valid_types
            assert 0 <= change["base_share"] <= 1
            assert 0 <= change["obs_share"] <= 1


def test_profile_update_preserves_skill_details(monkeypatch) -> None:
    captured: dict = {}

    def fake_save(candidate_id: str, skills: list[dict], projects: list[str]) -> dict:
        captured.update(candidate_id=candidate_id, skills=skills, projects=projects)
        return {"profileVersion": "saved", "matchId": "match-1", "overallScore": 0.8}

    monkeypatch.setattr(api_main, "save_profile", fake_save)
    response = TestClient(app).patch(
        "/api/v1/candidates/candidate-1/profile",
        json={
            "skills": [
                {
                    "name": "Python",
                    "status": "ready",
                    "level": "高级",
                    "years": 8,
                }
            ],
            "projects": ["Agent 平台"],
        },
    )
    assert response.status_code == 200
    assert captured["skills"][0] == {
        "name": "Python",
        "status": "ready",
        "level": "高级",
        "years": 8.0,
    }


def test_evaluation_overview_contract() -> None:
    response = TestClient(app).get("/api/v1/evaluation/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["datasets"]
    assert body["summary"] == {
        "total": 136,
        "hits": 50,
        "errors": 86,
        "accuracy": 0.368,
        "baselineAccuracy": 0.449,
    }
    assert len(body["errors"]) == 6
    assert body["errors"][0]["label"] == "预测上升，实际下降"
    assert body["errors"][0]["categoryLabel"] == "方向判断相反"
    assert body["errors"][0]["count"] == 25
    assert len(body["cases"]) == 136
    assert body["cases"][0]["skillLabel"] != body["cases"][0]["skillId"]
    assert [item["id"] for item in body["datasets"]] == [
        "role",
        "domain",
        "event",
        "trend",
    ]
    sample_evaluations = {item["id"]: item for item in body["sampleEvaluations"]}
    assert sample_evaluations["role"]["summary"]["errors"] == 22
    assert sample_evaluations["domain"]["summary"]["errors"] == 2
    assert sample_evaluations["event"]["summary"]["errors"] == 0
    assert len(sample_evaluations["role"]["cases"]) == 100


def test_dataset_overview_contract() -> None:
    response = TestClient(app).get("/api/v1/datasets/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["total_datasets"] >= 5
    assert {item["id"] for item in body["datasets"]} >= {"jd", "evaluation", "capability"}


def test_dataset_detail_and_source_stats(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    client = TestClient(app)
    detail = client.get("/api/v1/datasets/temporal")
    assert detail.status_code == 200
    body = detail.json()
    assert body["dataset"]["version"]
    assert body["versions"][0]["manifest_hash"]
    assert "files" not in body["versions"][0]["manifest"]

    source = client.get("/api/v1/datasets/temporal/sources/wechat-mp")
    assert source.status_code == 200
    assert source.json()["stats"]["evidence_count"] > 500
    assert source.json()["stats"]["attribution"] == "exact"

    unavailable = client.get("/api/v1/datasets/jd/sources/jd-corp")
    assert unavailable.status_code == 200
    assert unavailable.json()["stats"]["attribution"] == "unavailable"

    assert client.get("/api/v1/datasets/unknown").status_code == 404


def test_publish_job_idempotent_and_unknown_404(isolated_review_log) -> None:
    client = TestClient(app)
    # 已发布过的默认草稿：幂等返回既有 PUBLISHED 版本而非 409
    ok = client.post(
        "/api/v1/jobs/default/versions/v2/publish",
        json={"reviewer": "pytest", "note": "幂等回归"},
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["versionId"] == "ai-agent-v2"
    assert body["publishedAt"]
    assert isinstance(body["reviewActionIds"], list)
    # 复发仍幂等（发布后不可变，不得重复固化）
    again = client.post("/api/v1/jobs/default/versions/v2/publish", json={})
    assert again.status_code == 200
    assert again.json()["versionId"] == "ai-agent-v2"
    # 未知草稿 404
    missing = client.post("/api/v1/jobs/unknown/versions/v9/publish", json={})
    assert missing.status_code == 404


def test_temporal_dataset_contract_camel_top_level() -> None:
    """前端契约：/temporal/dataset 顶层键 camelCase，内层对象 snake_case。"""
    response = TestClient(app).get("/api/v1/temporal/dataset")
    assert response.status_code == 200
    body = response.json()
    assert "backtestRecords" in body
    assert "backtest_records" not in body
    for key in ("forecasts", "signals", "suggestions", "backtests"):
        assert key in body, f"缺少顶层键 {key}"
    if body["suggestions"]:
        first = body["suggestions"][0]
        # 前端渲染硬依赖：缺 evidence_ids 会导致建议页崩溃
        assert "evidence_ids" in first
        assert "suggestion_id" in first
        assert "review_status" in first
    if body["backtestRecords"]:
        assert "skill_id" in body["backtestRecords"][0]


def test_temporal_signals_returns_complete_history(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    response = TestClient(app).get("/api/v1/temporal/signals")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == len(body["signals"])
    assert body["total"] == len({signal["signal_id"] for signal in body["signals"]})
    assert body["total"] > 500
    assert body["earliest_observed_at"] < body["latest_observed_at"]


def test_evidence_search_and_pipeline_run_detail() -> None:
    client = TestClient(app)
    facets = client.get("/api/v1/evidence/facets")
    assert facets.status_code == 200
    assert any(item["value"] == "wechat-mp" for item in facets.json()["sources"])
    assert facets.json()["earliestPublishedAt"] < facets.json()["latestPublishedAt"]

    evidence = client.get("/api/v1/evidence?source_id=wechat-mp&limit=2")
    assert evidence.status_code == 200
    evidence_body = evidence.json()
    assert evidence_body["total"] > 500
    assert len(evidence_body["items"]) == 2
    assert all(item["source"] == "wechat-mp" for item in evidence_body["items"])
    assert all("claimType" in item for item in evidence_body["items"])

    dated = client.get(
        "/api/v1/evidence?source_id=wechat-mp&date_from=2026-08-01&date_to=2026-08-31&limit=20"
    )
    assert dated.status_code == 200
    assert dated.json()["items"]
    assert all(
        "2026-08-01" <= item["publishedAt"][:10] <= "2026-08-31" for item in dated.json()["items"]
    )

    runs = client.get("/api/v1/pipeline-runs?limit=1&since_days=3650").json()["runs"]
    assert runs
    run_id = runs[0]["run_id"]
    detail = client.get(f"/api/v1/pipeline-runs/{run_id}")
    assert detail.status_code == 200
    run_body = detail.json()
    assert run_body["run"]["run_id"] == run_id
    assert run_body["event_count"] == len(run_body["events"])
    assert {item["name"] for item in run_body["artifacts"]} >= {"events.jsonl"}
    assert client.get("/api/v1/pipeline-runs/../bad").status_code == 404


def test_temporal_suggestion_review_unknown_id_404() -> None:
    response = TestClient(app).post(
        "/api/v1/temporal/suggestions/sug-nonexistent/review",
        json={"decision": "accepted"},
    )
    assert response.status_code == 404


def test_skills_graph_switches_job_and_unknown_404() -> None:
    """能力全景岗位切换契约：?job= 指定岗位版本，未知版本 404。"""
    client = TestClient(app)

    body = client.get("/api/v1/skills/graph?job=llm-algo-v2").json()
    assert body["context"]["jobTitle"] == "大模型算法工程师"
    assert body["context"]["targetVersion"] == "llm-algo-v2"
    # 根节点是岗位本身，label 与岗位标题一致
    root = next(n for n in body["nodes"] if n["id"] == "root")
    assert root["label"] == "大模型算法工程师"

    # 默认岗位仍为 ai-agent-v2，不受新参数影响
    default = client.get("/api/v1/skills/graph").json()
    assert default["context"]["targetVersion"] == "ai-agent-v2"

    response = client.get("/api/v1/skills/graph?job=nonexistent-v9")
    assert response.status_code == 404
    assert "nonexistent-v9" in response.json()["detail"]


def test_task_decision_unknown_id_404() -> None:
    response = TestClient(app).post(
        "/api/v1/tasks/task-nonexistent/decision",
        json={"decision": "ACCEPT"},
    )
    assert response.status_code == 404


def test_career_resume_advice() -> None:
    draft = {
        "name": "张三",
        "title": "AI 应用工程师",
        "summary": "3 年 LLM 应用开发",
        "skills": ["Python", "LangChain"],
        "experiences": [
            {
                "company": "某公司",
                "role": "后端",
                "period": "2022-2024",
                "bullets": ["做 RAG 问答 10w 日活"],
            }
        ],
        "projects": [],
        "education": [],
    }
    response = TestClient(app).post(
        "/api/v1/career/resume/advice?job_version_id=ai-agent-v2", json=draft
    )
    assert response.status_code == 200
    body = response.json()
    assert body["required_total"] >= 4 and 0 <= body["required_covered"] <= body["required_total"]
    kinds = {a["kind"] for a in body["advice"]}
    assert "coverage" in kinds  # 必备未全覆盖 -> 覆盖差建议存在
    assert body["advice"][0]["evidence"]  # 建议必须带证据


def test_career_resume_advice_unknown_job_404() -> None:
    response = TestClient(app).post(
        "/api/v1/career/resume/advice?job_version_id=nonexistent", json={}
    )
    assert response.status_code == 404


def test_career_resume_render_pdf() -> None:
    import shutil

    if not shutil.which("pandoc"):
        import pytest

        pytest.skip("CI 无 pandoc，渲染链路本地/容器验证")
    draft = {
        "name": "张三",
        "title": "AI 应用工程师",
        "skills": ["Python"],
        "experiences": [],
        "projects": [],
        "education": [],
    }
    response = TestClient(app).post("/api/v1/career/resume/render", json=draft)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content[:5] == b"%PDF-"


def test_xlzsz_certs_contract() -> None:
    response = TestClient(app).get("/api/v1/xlzsz/certs", params={"skill_id": "cap_04"})
    assert response.status_code == 200
    body = response.json()
    assert body["skill_id"] == "cap_04"
    assert body["skill_name"] == "AI Agent"
    names = [c["name"] for c in body["certs"]]
    assert "智能体工程师认证" in names
    first = body["certs"][0]
    assert first["issuer"]  # 每条可回链颁发机构
    assert first["url"]


def test_xlzsz_contests_contract() -> None:
    response = TestClient(app).get("/api/v1/xlzsz/contests", params={"skill_id": "cap_04"})
    assert response.status_code == 200
    body = response.json()
    assert len(body["contests"]) >= 1
    assert any("挑战杯" in c["name"] or "讯飞" in c["name"] for c in body["contests"])


def test_xlzsz_unknown_skill_returns_empty() -> None:
    response = TestClient(app).get("/api/v1/xlzsz/certs", params={"skill_id": "cap_99"})
    assert response.status_code == 200
    assert response.json()["certs"] == []
    response = TestClient(app).get("/api/v1/xlzsz/contests", params={"skill_id": "cap_99"})
    assert response.status_code == 200
    assert response.json()["contests"] == []


def test_training_output_recommends_certs() -> None:
    body = TestClient(app).get("/api/v1/jobs/ai-agent-v2/training-output").json()
    reqs = body["cert_requirements"]
    assert reqs, "岗位必须有证书要求条目"
    with_cert = [r for r in reqs if r.get("recommended_certs")]
    assert with_cert, "至少一项能力要求推荐真实证书"
    assert any("认证" in c for r in with_cert for c in r["recommended_certs"])
