import { redirect } from "next/navigation";

// 标注质量看板已并入评测与质量页（/evaluation）。
export default function QualityPage() {
  redirect("/evaluation");
}
