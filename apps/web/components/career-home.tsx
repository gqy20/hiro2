"use client";

import Link from "next/link";
import { ArrowRight, CheckCircle } from "@phosphor-icons/react";
import type { DiagnosisFixture } from "@/lib/diagnosis";

export function CareerHome({ fixture }: { fixture: DiagnosisFixture }) {
  const gaps = fixture.report.gaps.filter((gap) => gap.priority === "high");
  const focus = gaps[0] ?? fixture.report.gaps[0];
  return (
    <section className="career-home" aria-labelledby="career-home-title">
      <header className="career-home-heading">
        <div>
          <h1 id="career-home-title">
            {fixture.job.title} <span>{fixture.job.version}</span>
          </h1>
          <p>已发布岗位标准 · 基于你的画像生成成长计划。</p>
        </div>
        <Link className="career-home-profile-link" href="/profile">
          编辑我的画像 <ArrowRight size={16} />
        </Link>
      </header>
      <div className="career-home-grid">
        <Link className="career-next-action" href="/diagnosis">
          <span>下一步</span>
          <strong>{focus?.skill ?? "继续完善画像"}</strong>
          <p>
            {focus?.reason ||
              "补充项目、作品或评测结果后，重新判断你的投递基础。"}
          </p>
          <b>
            开始补齐 <ArrowRight size={16} />
          </b>
        </Link>
        <Link className="career-progress-card" href="/diagnosis">
          <span>投递基础</span>
          <strong>{Math.round(fixture.report.overallScore * 100)}%</strong>
          <p>
            已具备{" "}
            {
              fixture.candidate.skills.filter((s) => s.status === "ready")
                .length
            }{" "}
            项能力
          </p>
          <b>
            查看完整诊断 <ArrowRight size={16} />
          </b>
        </Link>
      </div>
      <section className="career-home-steps">
        <div className="section-heading">
          <h2>完成一次能力提升</h2>
        </div>
        <ol>
          <li>
            <CheckCircle size={18} />
            <div>
              <strong>确认画像</strong>
              <span>检查技能、年限和能力证明</span>
            </div>
          </li>
          <li>
            <ArrowRight size={18} />
            <div>
              <strong>完成练习</strong>
              <span>围绕关键缺口完成一个可展示项目</span>
            </div>
          </li>
          <li>
            <ArrowRight size={18} />
            <div>
              <strong>重新诊断</strong>
              <span>用新证明更新投递基础</span>
            </div>
          </li>
        </ol>
      </section>
    </section>
  );
}
