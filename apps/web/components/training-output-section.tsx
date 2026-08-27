"use client";

// F-T3.6 下游输出：发布成功后拉取岗位标准（JD 模板 / 培养任务 / 能力证明要求）。
// 字段沿用后端 model_dump 的 snake_case，仅在本视图消费，不进共享 DTO。

import { useEffect, useState } from "react";
import { Tag } from "antd";

import { apiFetch, isMockMode } from "@/lib/api/client";

type TrainingOutput = {
  job_version_id: string;
  job_title: string;
  jd_template: {
    responsibilities: string[];
    required_skills: { name: string; weight: number }[];
    preferred_skills: { name: string; weight: number }[];
    scenarios: string[];
  };
  training_tasks: {
    task_id: string;
    name: string;
    skill_name: string;
    level: string;
    learn: string;
    practice: string;
    evaluate: string;
    certify: string;
  }[];
  cert_requirements: {
    skill_name: string;
    evidence_types: string[];
    min_quality: number;
  }[];
};

export function TrainingOutputSection({ versionId }: { versionId: string }) {
  const [data, setData] = useState<TrainingOutput | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isMockMode() || !versionId) return;
    apiFetch<TrainingOutput>(
      `/jobs/${encodeURIComponent(versionId)}/training-output`,
    )
      .then(setData)
      .catch((err: Error) => setError(err.message));
  }, [versionId]);

  if (isMockMode()) {
    return (
      <section aria-labelledby="training-output-title" className="review-summary">
        <h2 id="training-output-title">下游输出</h2>
        <p className="publish-hint">接入真实后端后，发布完成即生成 JD 模板与培养任务。</p>
      </section>
    );
  }
  if (error) {
    return (
      <section aria-labelledby="training-output-title" className="review-summary">
        <h2 id="training-output-title">下游输出</h2>
        <p className="publish-hint">下游输出暂不可用：{error}</p>
      </section>
    );
  }
  if (!data) {
    return (
      <section aria-labelledby="training-output-title" className="review-summary">
        <h2 id="training-output-title">下游输出</h2>
        <p className="publish-hint">正在生成 JD 模板与培养任务…</p>
      </section>
    );
  }

  return (
    <section aria-labelledby="training-output-title" className="review-summary">
      <h2 id="training-output-title">{`下游输出 · ${data.job_title}`}</h2>
      <div className="training-block">
        <h3>JD 模板</h3>
        <p className="publish-hint">
          {`职责 ${data.jd_template.responsibilities.length} 条 · 必备 ${data.jd_template.required_skills.length} 项 / 加分 ${data.jd_template.preferred_skills.length} 项`}
        </p>
        <div className="training-tags">
          {data.jd_template.required_skills.map((s) => (
            <Tag color="gold" key={s.name}>{`${s.name} ${s.weight}`}</Tag>
          ))}
          {data.jd_template.preferred_skills.map((s) => (
            <Tag key={s.name}>{`${s.name} ${s.weight}`}</Tag>
          ))}
        </div>
      </div>
      <div className="training-block">
        <h3>培养任务（学练赛证）</h3>
        <ul className="training-tasks">
          {data.training_tasks.map((t) => (
            <li key={t.task_id}>
              <span className="task-name">{`${t.name} · ${t.skill_name}`}</span>
              <Tag>{t.level}</Tag>
              <p className="publish-hint">{`学 ${t.learn} / 练 ${t.practice} / 赛 ${t.evaluate} / 证 ${t.certify}`}</p>
            </li>
          ))}
        </ul>
      </div>
      <div className="training-block">
        <h3>能力证明要求</h3>
        <div className="training-tags">
          {data.cert_requirements.map((c) => (
            <Tag key={c.skill_name}>
              {`${c.skill_name}：${c.evidence_types.join("/")} ≥ ${c.min_quality}`}
            </Tag>
          ))}
        </div>
      </div>
    </section>
  );
}
