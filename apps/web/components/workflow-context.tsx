import Link from "next/link";

export function WorkflowContext({
  eyebrow,
  title,
  stage,
  next,
  href,
}: {
  eyebrow: string;
  title: string;
  stage: string;
  next: string;
  href?: string;
}) {
  return (
    <div className="workflow-context" aria-label="当前流程">
      <div className="workflow-context-title">
        <span>{eyebrow}</span>
        <strong>{title}</strong>
      </div>
      <div className="workflow-context-stage">
        <span>当前阶段</span>
        <b>{stage}</b>
      </div>
      <div className="workflow-context-next">
        <span>下一步</span>
        {href ? <Link href={href}>{next} →</Link> : <b>{next}</b>}
      </div>
    </div>
  );
}
