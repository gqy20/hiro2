import { redirect } from "next/navigation";

/* 时间情报直接进入首个工作视图，子页面之间通过共享导航切换。 */
export default function TemporalPage() {
  redirect("/temporal/signals");
}
