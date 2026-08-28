"use client";

import { useMemo, useState } from "react";
import { DataNav } from "@/components/data-nav";
import type { DatasetItem, DatasetOverview } from "@/lib/datasets";

type Props = Readonly<{ overview: DatasetOverview }>;

function formatNumber(n: number): string {
  return n.toLocaleString("zh-CN");
}

function statusClass(status: string): string {
  if (status.includes("冻结")) return "data-source-status is-frozen";
  if (status.includes("审核")) return "data-source-status is-reviewed";
  if (status.includes("部分")) return "data-source-status is-partial";
  return "data-source-status";
}

export function DataSourcesWorkbench({ overview }: Props) {
  const [category, setCategory] = useState<string>("all");
  const [status, setStatus] = useState<string>("all");
  const [query, setQuery] = useState<string>("");

  const categories = useMemo(() => {
    const set = new Set(overview.datasets.map((d) => d.category));
    return ["all", ...Array.from(set)];
  }, [overview.datasets]);

  const statuses = useMemo(() => {
    const set = new Set(overview.datasets.map((d) => d.status));
    return ["all", ...Array.from(set)];
  }, [overview.datasets]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return overview.datasets.filter((d) => {
      if (category !== "all" && d.category !== category) return false;
      if (status !== "all" && d.status !== status) return false;
      if (q && !`${d.name} ${d.id} ${d.source}`.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [overview.datasets, category, status, query]);

  return (
    <section className="data-sources" aria-labelledby="data-sources-title">
      <h1 id="data-sources-title" className="data-sources-title">
        数据来源
      </h1>
      <DataNav />

      <div className="data-sources-toolbar" role="group" aria-label="筛选">
        <label className="data-sources-field">
          <span>类型</span>
          <select
            onChange={(e) => setCategory(e.target.value)}
            value={category}
          >
            {categories.map((c) => (
              <option key={c} value={c}>
                {c === "all" ? "全部" : c}
              </option>
            ))}
          </select>
        </label>
        <label className="data-sources-field">
          <span>状态</span>
          <select onChange={(e) => setStatus(e.target.value)} value={status}>
            {statuses.map((s) => (
              <option key={s} value={s}>
                {s === "all" ? "全部" : s}
              </option>
            ))}
          </select>
        </label>
        <label className="data-sources-field data-sources-search">
          <span>搜索</span>
          <input
            onChange={(e) => setQuery(e.target.value)}
            placeholder="按名称 / 来源搜索"
            type="search"
            value={query}
          />
        </label>
      </div>

      <div className="data-sources-table-wrap">
        <table className="data-sources-table">
          <thead>
            <tr>
              <th scope="col">名称</th>
              <th scope="col">类型</th>
              <th scope="col" className="num">记录数</th>
              <th scope="col">版本</th>
              <th scope="col">状态</th>
              <th scope="col">最近更新</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td className="data-sources-empty" colSpan={6}>
                  没有匹配的来源
                </td>
              </tr>
            ) : (
              filtered.map((d) => (
                <SourceRow dataset={d} key={d.id} />
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SourceRow({ dataset }: { dataset: DatasetItem }) {
  return (
    <tr>
      <th scope="row">
        <span className="data-source-row-name">{dataset.name}</span>
        <small className="data-source-row-source">{dataset.source}</small>
      </th>
      <td>{dataset.category}</td>
      <td className="num">{formatNumber(dataset.records)}</td>
      <td>{dataset.version}</td>
      <td>
        <span className={statusClass(dataset.status)}>{dataset.status}</span>
      </td>
      <td className="data-source-row-date">
        {dataset.updated_at ? dataset.updated_at.slice(0, 10) : "—"}
      </td>
    </tr>
  );
}
