"use client";

import Link from "next/link";
import { ArrowRight, CheckCircle } from "@phosphor-icons/react";
import type { DiagnosisFixture } from "@/lib/diagnosis";

export function CareerHomeEmpty() {
  return (
    <section className="career-home" aria-labelledby="career-home-title">
      <header className="career-home-heading">
        <div>
          <h1 id="career-home-title">开始你的成长诊断</h1>
          <p>选择目标岗位，或上传简历直接开始。</p>
        </div>
      </header>
      <div className="career-home-grid">
        <Link className="career-next-action" href="/career/jobs">
          <span>第一步</span>
          <strong>选择目标岗位</strong>
          <p>浏览全部已发布岗位标准，找到你的方向。</p>
          <b>
            查看岗位 <ArrowRight size={16} />
          </b>
        </Link>
        <Link className="career-progress-card" href="/resumes">
          <span>已有简历</span>
          <strong>上传简历开始诊断</strong>
          <p>支持 PDF / DOCX，解析结果可修正。</p>
          <b>
            上传简历 <ArrowRight size={16} />
          </b>
        </Link>
      </div>
    </section>
  );
}

export function CareerHome({ fixture }: { fixture: DiagnosisFixture }) {
  const gaps = fixture.report.gaps.filter((gap) => gap.priority === "high");
  const focus = gaps[0] ?? fixture.report.gaps[0];
  const required =
    fixture.report.requiredTotal && fixture.report.requiredTotal > 0
      ? `${fixture.report.requiredMet ?? 0}/${fixture.report.requiredTotal}`
      : null;
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
          <span>{required ? "必备能力" : "投递基础"}</span>
          <strong>
            {required ?? `${Math.round(fixture.report.overallScore * 100)}%`}
          </strong>
          <p>
            已具备{" "}
            {
              fixture.candidate.skills.filter((s) => s.status === "ready")
                .length
            }{" "}
            项能力
            {required
              ? ` · 投递基础 ${Math.round(fixture.report.overallScore * 100)}%`
              : ""}
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
