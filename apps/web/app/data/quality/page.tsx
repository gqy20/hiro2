import { redirect } from "next/navigation";

// 标注质量内容已并入评测与质量页（/evaluation）。
export default function DataQualityPage() {
  redirect("/evaluation");
}
