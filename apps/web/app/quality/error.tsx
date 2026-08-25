"use client";

import { useEffect } from "react";
import { Button, Result } from "antd";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    if (error.digest) {
      console.error(`[hiro2] quality load failed, digest=${error.digest}`);
    }
  }, [error]);

  return (
    <Result
      status="warning"
      title="质量看板加载失败"
      subTitle={
        error.digest
          ? `错误编号：${error.digest}，可稍后重试或联系管理员。`
          : "请检查后端服务或网络后重试。"
      }
      extra={
        <Button type="primary" onClick={() => reset()}>
          重试
        </Button>
      }
    />
  );
}