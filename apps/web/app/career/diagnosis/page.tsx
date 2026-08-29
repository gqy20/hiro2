import { DiagnosisPageView } from "@/components/diagnosis-page";

export default async function CareerDiagnosisPage({
  searchParams,
}: Readonly<{
  searchParams: Promise<{ state?: string; candidate?: string; job?: string }>;
}>) {
  return <DiagnosisPageView mode="career" searchParams={searchParams} />;
}
