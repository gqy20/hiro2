import { AppShell } from "@/components/app-shell";

export default function TemporalLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <AppShell>
      <div className="temporal-route-shell">{children}</div>
    </AppShell>
  );
}
