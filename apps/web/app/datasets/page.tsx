import { redirect } from "next/navigation";

// 数据资产页已并入数据工作区总览（/data）的数据集目录区块。
export default function DatasetsPage() {
  redirect("/data");
}
