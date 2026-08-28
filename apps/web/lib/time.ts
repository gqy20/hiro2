// 统一时间格式化：业务受众在国内，所有展示时间固定按 Asia/Shanghai，
// 不再用 toISOString()（UTC，差 8 小时）。

const TZ = "Asia/Shanghai";

const dateFmt = new Intl.DateTimeFormat("en-CA", {
  timeZone: TZ,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

const timeFmt = new Intl.DateTimeFormat("zh-CN", {
  timeZone: TZ,
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

function parse(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** "08-28 19:56"（Asia/Shanghai），非法输入原样返回 */
export function formatTime(iso: string | null | undefined): string {
  const date = parse(iso);
  if (!date) return iso ?? "";
  return timeFmt.format(date).replace(/\//g, "-");
}

/** "2026-08-28"（Asia/Shanghai），用于按日分组 */
export function formatDate(iso: string | null | undefined): string {
  const date = parse(iso);
  if (!date) return "";
  return dateFmt.format(date);
}

/** 当前日期（Asia/Shanghai），"2026-08-28" */
export function todayStr(): string {
  return dateFmt.format(new Date());
}
