import { AppShell } from "@/components/app-shell";
import { TemporalNav } from "@/components/temporal-nav";

export default function TemporalLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <AppShell>
      <div className="temporal-route-shell">
        <TemporalNav />
        {children}
      </div>
    </AppShell>
  );
}
