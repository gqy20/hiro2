"use client";

import { useEffect, useState } from "react";
import { Database, FileText, ShieldCheck, X } from "@phosphor-icons/react";
import type { DatasetItem, DatasetOverview } from "@/lib/datasets";

function formatNumber(value: number) {
  return new Intl.NumberFormat("zh-CN").format(value);
}

function statusClass(status: string) {
  if (status === "部分解析") return "dataset-status dataset-status-warning";
  if (status === "已冻结" || status === "已审核")
    return "dataset-status dataset-status-success";
  return "dataset-status";
}

export function DatasetWorkbench({
  overview,
  embedded = false,
}: {
  overview: DatasetOverview;
  embedded?: boolean;
}) {
  const [selected, setSelected] = useState<DatasetItem | null>(null);

  // Esc 关闭抽屉
  useEffect(() => {
    if (!selected) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelected(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selected]);
  const maxRecords = Math.max(
    ...overview.datasets.map((item) => item.records),
    1,
  );
  return (
    <section
      className="dataset-workbench"
      {...(embedded
        ? { "aria-label": "数据集目录" }
        : { "aria-labelledby": "dataset-title" })}
    >
      {embedded ? null : (
        <header className="page-heading dataset-heading">
          <div>
            <h1 id="dataset-title">数据资产</h1>
            <p>岗位能力分析使用的数据，从来源到评测均可追溯。</p>
          </div>
          <span className="dataset-heading-meta">内部质量工作区</span>
        </header>
      )}

      {embedded ? null : (
        <div className="dataset-summary" aria-label="数据资产总览">
          <div>
            <span>数据集</span>
            <strong>{overview.total_datasets}</strong>
            <small>个数据集</small>
          </div>
          <div>
            <span>记录总量</span>
            <strong>{formatNumber(overview.total_records)}</strong>
            <small>条记录</small>
          </div>
          <div>
            <span>可用数据集</span>
            <strong>{overview.ready_datasets}</strong>
            <small>个已就绪</small>
          </div>
          <div>
            <span>待处理</span>
            <strong>{formatNumber(overview.pending_records)}</strong>
            <small>条待处理记录</small>
          </div>
        </div>
      )}

      {embedded ? null : (
        <div className="dataset-main-grid">
          <section
            className="dataset-panel dataset-chart-panel"
            aria-labelledby="dataset-chart-title"
          >
            <div className="dataset-panel-heading">
              <h2 id="dataset-chart-title">数据规模</h2>
              <span>按数据集</span>
            </div>
            <div className="dataset-bars">
              {overview.datasets.map((item) => (
                <button
                  className="dataset-bar-row"
                  key={item.id}
                  onClick={() => setSelected(item)}
                  type="button"
                >
                  <span className="dataset-bar-label">{item.name}</span>
                  <span className="dataset-bar-track">
                    <i
                      style={{
                        width: `${Math.max((item.records / maxRecords) * 100, 2)}%`,
                      }}
                    />
                  </span>
                  <strong>{formatNumber(item.records)}</strong>
                </button>
              ))}
            </div>
          </section>

          <section
            className="dataset-panel dataset-flow-panel"
            aria-labelledby="dataset-flow-title"
          >
            <div className="dataset-panel-heading">
              <h2 id="dataset-flow-title">数据流转</h2>
              <span>可重建链路</span>
            </div>
            <div className="dataset-flow" aria-label="原始数据到评测的处理链路">
              {[
                ["来源", "采集与导入", "source"],
                ["标准化", "清洗与归一", "normalize"],
                ["证据", "时间与质量", "evidence"],
                ["应用", "岗位与评测", "publish"],
              ].map(([title, detail, key], index) => (
                <div className="dataset-flow-step" key={key}>
                  <span>{index + 1}</span>
                  <strong>{title}</strong>
                  <small>{detail}</small>
                </div>
              ))}
            </div>
            <p className="dataset-flow-note">
              <Database size={15} /> 每条正式结论都关联数据集版本与运行记录
            </p>
          </section>
        </div>
      )}

      <section
        className="dataset-panel dataset-table-panel"
        aria-labelledby="dataset-table-title"
      >
        <div className="dataset-panel-heading">
          <h2 id="dataset-table-title">数据集目录</h2>
          <span>{overview.datasets.length} 个数据集</span>
        </div>
        <div className="dataset-table-wrap">
          <table className="t-table">
            {/* 固定列宽：t-table 为 fixed 布局，宽度按各列内容字数标定 */}
            <colgroup>
              <col className="col-name" />
              <col className="col-category" />
              <col className="col-size" />
              <col className="col-version" />
              <col className="col-format" />
              <col className="col-status" />
              <col className="col-quality" />
            </colgroup>
            <thead>
              <tr>
                <th>数据集</th>
                <th>类型</th>
                <th>规模</th>
                <th>版本</th>
                <th>格式</th>
                <th>状态</th>
                <th>质量</th>
              </tr>
            </thead>
            <tbody>
              {overview.datasets.map((item) => (
                <tr
                  key={item.id}
                  onClick={() => setSelected(item)}
                  tabIndex={0}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setSelected(item);
                    }
                  }}
                >
                  <th scope="row">
                    <strong>{item.name}</strong>
                    <small>{item.source}</small>
                  </th>
                  <td>{item.category}</td>
                  <td className="dataset-number num">
                    {formatNumber(item.records)}
                  </td>
                  <td>
                    <code>{item.version}</code>
                  </td>
                  <td>
                    <span className="dataset-format">
                      {item.formats.join(" · ")}
                    </span>
                  </td>
                  <td>
                    <span className={statusClass(item.status)}>
                      {item.status}
                    </span>
                  </td>
                  <td>
                    <span className="dataset-quality">
                      <i style={{ width: `${item.quality}%` }} />
                      {item.quality}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {selected && (
        <div
          className="dataset-drawer-backdrop"
          role="presentation"
          onClick={() => setSelected(null)}
        >
          <aside
            className="dataset-drawer"
            role="dialog"
            aria-modal="true"
            aria-labelledby="dataset-detail-title"
            onClick={(event) => event.stopPropagation()}
          >
            <header>
              <div>
                <span className="dataset-drawer-kicker">
                  <FileText size={14} /> 数据集详情
                </span>
                <h2 id="dataset-detail-title">{selected.name}</h2>
              </div>
              <button
                aria-label="关闭详情"
                onClick={() => setSelected(null)}
                type="button"
              >
                <X size={20} />
              </button>
            </header>
            <div className="dataset-detail-status">
              <span className={statusClass(selected.status)}>
                {selected.status}
              </span>
              <code>{selected.version}</code>
            </div>
            <dl>
              <div>
                <dt>数据域</dt>
                <dd>{selected.category}</dd>
              </div>
              <div>
                <dt>记录数</dt>
                <dd>{formatNumber(selected.records)}</dd>
              </div>
              <div>
                <dt>数据格式</dt>
                <dd>{selected.formats.join("、")}</dd>
              </div>
              <div>
                <dt>来源</dt>
                <dd>{selected.source}</dd>
              </div>
              <div>
                <dt>质量门</dt>
                <dd>
                  <ShieldCheck size={16} /> {selected.quality}% 通过
                </dd>
              </div>
            </dl>
            <div className="dataset-detail-section">
              <h3>使用说明</h3>
              <p>
                该数据集作为岗位能力演化与评测流程的输入，详情字段和原始文件仅对内部质量角色开放。
              </p>
            </div>
          </aside>
        </div>
      )}
    </section>
  );
}
