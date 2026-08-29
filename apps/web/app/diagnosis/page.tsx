import { DiagnosisPageView } from "@/components/diagnosis-page";

export const metadata = { title: "候选诊断" };

export default async function DiagnosisPage({
  searchParams,
}: Readonly<{
  searchParams: Promise<{ state?: string; candidate?: string; job?: string }>;
}>) {
  return <DiagnosisPageView mode="recruiting" searchParams={searchParams} />;
}
