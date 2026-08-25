import { Skeleton } from "antd";

export default function Loading() {
  return (
    <section className="page-loading" aria-busy="true" aria-live="polite">
      <Skeleton active paragraph={{ rows: 8 }} />
    </section>
  );
}
