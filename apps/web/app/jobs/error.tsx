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
    // 服务端日志已记录完整 error；这里只在客户端 console 输出 digest 帮助定位。
    if (error.digest) {
      console.error(`[hiro2] job update load failed, digest=${error.digest}`);
    }
  }, [error]);

  return (
    <Result
      status="warning"
      title="岗位更新加载失败"
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