"use client";

import { useMemo, useState } from "react";
import type { DatasetItem, DatasetOverview } from "@/lib/datasets";
import { SourceDrawer } from "@/components/data-flow-map";

type Props = Readonly<{ overview: DatasetOverview }>;

type SortKey =
  "name" | "category" | "records" | "version" | "status" | "updated_at";

// 可筛选的列（控制即列头）：类型、状态
type FilterKey = "category" | "status";

const SORT_COLUMNS: {
  key: SortKey;
  label: string;
  numeric?: boolean;
  filter?: FilterKey;
}[] = [
  { key: "name", label: "名称" },
  { key: "category", label: "类型", filter: "category" },
  { key: "records", label: "记录数", numeric: true },
  { key: "version", label: "版本" },
  { key: "status", label: "状态", filter: "status" },
  { key: "updated_at", label: "最近更新" },
];

function sortValue(item: DatasetItem, key: SortKey): string | number {
  if (key === "records") return item.records;
  return item[key] ?? "";
}

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
  const [sortKey, setSortKey] = useState<SortKey>("records");
  const [sortDesc, setSortDesc] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);

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
    const rows = overview.datasets.filter((d) => {
      if (category !== "all" && d.category !== category) return false;
      if (status !== "all" && d.status !== status) return false;
      if (q && !`${d.name} ${d.id} ${d.source}`.toLowerCase().includes(q))
        return false;
      return true;
    });
    const dir = sortDesc ? -1 : 1;
    return rows.sort((a, b) => {
      const va = sortValue(a, sortKey);
      const vb = sortValue(b, sortKey);
      if (typeof va === "number" && typeof vb === "number")
        return (va - vb) * dir;
      return String(va).localeCompare(String(vb), "zh-CN") * dir;
    });
  }, [overview.datasets, category, status, query, sortKey, sortDesc]);

  function toggleSort(key: SortKey) {
    if (key === sortKey) setSortDesc((d) => !d);
    else {
      setSortKey(key);
      setSortDesc(key === "records");
    }
  }

  const selectedDataset = selected
    ? overview.datasets.find((d) => d.id === selected)
    : undefined;

  // 再点同一行收起
  function toggleSelect(id: string) {
    setSelected((prev) => (prev === id ? null : id));
  }

  return (
    <section className="data-sources" aria-labelledby="data-sources-title">
      <div className="data-sources-head">
        <h1 id="data-sources-title" className="sr-only">
          数据来源
        </h1>
        <input
          aria-label="搜索来源"
          className="data-sources-search"
          onChange={(e) => setQuery(e.target.value)}
          placeholder="按名称 / 来源搜索"
          type="search"
          value={query}
        />
        <span className="data-sources-count">
          {filtered.length} / {overview.datasets.length} 个来源
        </span>
      </div>

      <div className="data-sources-layout">
        <div className="data-sources-table-wrap">
          <table className="t-table data-sources-table">
            {/* 固定列宽：筛选改变行内容时列宽不再重算跳动 */}
            <colgroup>
              <col className="col-name" />
              <col className="col-category" />
              <col className="col-records" />
              <col className="col-version" />
              <col className="col-status" />
              <col className="col-updated" />
            </colgroup>
            <thead>
              <tr>
                {SORT_COLUMNS.map((col) => {
                  const isFilter = Boolean(col.filter);
                  const sorted = !isFilter && sortKey === col.key;
                  return (
                    <th
                      aria-sort={
                        sorted
                          ? sortDesc
                            ? "descending"
                            : "ascending"
                          : undefined
                      }
                      className={col.numeric ? "num" : undefined}
                      key={col.key}
                      scope="col"
                    >
                      {isFilter ? (
                        <select
                          aria-label={`按${col.label}筛选`}
                          className="col-filter"
                          onChange={(e) =>
                            col.filter === "category"
                              ? setCategory(e.target.value)
                              : setStatus(e.target.value)
                          }
                          value={col.filter === "category" ? category : status}
                        >
                          {(col.filter === "category"
                            ? categories
                            : statuses
                          ).map((s) => (
                            <option key={s} value={s}>
                              {s === "all" ? `${col.label} · 全部` : s}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <button
                          className={
                            sorted ? "table-sort is-active" : "table-sort"
                          }
                          onClick={() => toggleSort(col.key)}
                          type="button"
                        >
                          {col.label}
                          <span aria-hidden className="table-sort-arrow">
                            {sorted ? (sortDesc ? "↓" : "↑") : ""}
                          </span>
                        </button>
                      )}
                    </th>
                  );
                })}
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
                  <SourceRow
                    active={d.id === selected}
                    dataset={d}
                    key={d.id}
                    onSelect={() => toggleSelect(d.id)}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>

        {selectedDataset ? (
          <SourceDrawer
            dataset={selectedDataset}
            onClose={() => setSelected(null)}
          />
        ) : null}
      </div>
    </section>
  );
}

function SourceRow({
  dataset,
  active,
  onSelect,
}: {
  dataset: DatasetItem;
  active: boolean;
  onSelect: () => void;
}) {
  return (
    <tr
      aria-selected={active}
      className={active ? "is-active" : undefined}
      onClick={onSelect}
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect();
        }
      }}
    >
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
