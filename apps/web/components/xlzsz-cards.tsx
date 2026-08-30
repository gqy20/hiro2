"use client";

// 学练赛证"证/赛"段实体卡片：为每个能力缺口渲染可点击的权威证书与竞赛。
// 数据来自 CERTS.yml / CONTESTS.yml 映射（后端 learning_path 结构化产出），
// 每条带颁发方/主办方与官方链接。

export type XlzszCard = {
  name: string;
  issuer?: string;
  organizer?: string;
  url?: string;
};

function CardList({
  title,
  items,
  subtitleKey,
}: {
  title: string;
  items: XlzszCard[];
  subtitleKey: "issuer" | "organizer";
}) {
  if (!items.length) return null;
  return (
    <div className="xlzsz-cards">
      <span className="xlzsz-cards-title">{title}</span>
      <ul>
        {items.map((c) => {
          const subtitle = c[subtitleKey];
          const body = (
            <>
              <span className="xlzsz-card-name">{c.name}</span>
              {subtitle ? (
                <span className="xlzsz-card-org">{subtitle}</span>
              ) : null}
            </>
          );
          return (
            <li key={c.name}>
              {c.url ? (
                <a
                  className="xlzsz-card xlzsz-card-link"
                  href={c.url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {body}
                </a>
              ) : (
                <span className="xlzsz-card">{body}</span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function XlzszCards({
  certificates,
  contests,
}: {
  certificates?: XlzszCard[];
  contests?: XlzszCard[];
}) {
  if (!certificates?.length && !contests?.length) return null;
  return (
    <div className="xlzsz-cards-wrap">
      <CardList title="证" items={certificates ?? []} subtitleKey="issuer" />
      <CardList title="赛" items={contests ?? []} subtitleKey="organizer" />
    </div>
  );
}
