import { NewJobsWorkbench } from "@/components/new-jobs-workbench";
import { loadNewJobsFixture } from "@/lib/new-jobs-fixture";

export default async function NewJobsPage({
  searchParams,
}: Readonly<{ searchParams: Promise<{ state?: string }> }>) {
  const { state } = await searchParams;
  const variant = state === "empty" || state === "error" ? state : "ready";
  return (
    <NewJobsWorkbench
      fixture={await loadNewJobsFixture(variant)}
      state={variant}
    />
  );
}
