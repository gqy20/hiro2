"""datasets View Model 的来源通道挂载测试：明细来自 data/SOURCES.yml，不硬编码。"""

from backend.application.datasets import (
    DATASET_SOURCES,
    DatasetItem,
    _attach_sources,
    _source_registry,
)


def test_registry_reads_sources_yml():
    registry = _source_registry()
    assert "jd-corp" in registry
    corp = registry["jd-corp"]
    assert corp.type == "employer_site"
    assert corp.time_range == ["2026-01", "2026-08"]
    assert "字节" in corp.notes  # 真实登记数字在 notes 中，不由前端编造


def test_attach_sources_by_dataset():
    items = [
        DatasetItem(id="jd", name="招聘岗位", category="业务数据"),
        DatasetItem(id="resumes", name="简历档案", category="候选人数据"),
    ]
    _attach_sources(items)
    jd, resumes = items
    assert [s.id for s in jd.sources] == DATASET_SOURCES["jd"]
    # 受控候选人数据无外部来源登记，留空交给前端展示派生说明
    assert resumes.sources == []
