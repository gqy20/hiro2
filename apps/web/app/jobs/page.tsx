import { JobUpdateWorkbench } from "@/components/job-update-workbench";
import { loadJobUpdateFixture } from "@/lib/job-fixture";

export default async function JobUpdatePage() {
  const fixture = await loadJobUpdateFixture();
  return <JobUpdateWorkbench fixture={fixture} />;
}
