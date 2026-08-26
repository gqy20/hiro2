"use client";

import Link from "next/link";
import { ArrowRight, CheckCircle, Target } from "@phosphor-icons/react";
import type { DiagnosisFixture } from "@/lib/diagnosis";

export function CareerHome({ fixture }: { fixture: DiagnosisFixture }) {
  const gaps = fixture.report.gaps.filter((gap) => gap.priority === "high");
  const focus = gaps[0] ?? fixture.report.gaps[0];
  return (
    <section className="career-home" aria-labelledby="career-home-title">
      <header className="career-home-heading">
        <div><h1 id="career-home-title">为下一个岗位准备自己</h1><p>从已发布岗位标准出发，把能力差距变成可以完成的行动。</p></div>
        <Link className="career-home-profile-link" href="/profile">编辑我的画像 <ArrowRight size={16} /></Link>
      </header>
      <div className="career-home-grid">
        <Link className="career-target-card" href="/diagnosis">
          <Target size={22} /><span>当前目标岗位</span><strong>{fixture.job.title}</strong><small>{fixture.job.version} · 已发布岗位标准</small><b>继续诊断 <ArrowRight size={16} /></b>
        </Link>
        <Link className="career-progress-card" href="/diagnosis"><span>投递基础</span><strong>{Math.round(fixture.report.overallScore * 100)}%</strong><p>已具备 {fixture.candidate.skills.filter((s) => s.status === "ready").length} 项能力</p><b>查看差距 <ArrowRight size={16} /></b></Link>
        <Link className="career-focus-card" href="/diagnosis"><span>先补这一项</span><strong>{focus?.skill ?? "继续完善画像"}</strong><p>{focus?.reason || "补充项目证明后再重新诊断。"}</p><b>进入成长计划 <ArrowRight size={16} /></b></Link>
      </div>
      <section className="career-home-steps"><div className="section-heading"><h2>成长路径</h2><span>三步完成一次提升</span></div><ol><li><b>01</b><div><strong>确认画像</strong><span>检查技能、年限和项目证据</span></div><CheckCircle size={18} /></li><li><b>02</b><div><strong>完成练习</strong><span>按岗位缺口完成一个可展示项目</span></div><ArrowRight size={18} /></li><li><b>03</b><div><strong>重新诊断</strong><span>用新证明更新投递基础</span></div><ArrowRight size={18} /></li></ol></section>
    </section>
  );
}
