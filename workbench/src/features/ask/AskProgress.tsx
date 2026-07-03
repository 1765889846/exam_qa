import { Steps } from "antd";
import type { AskPhase } from "./types";

interface AskProgressProps {
  phase: AskPhase;
}

export function AskProgress({ phase }: AskProgressProps) {
  const current = phase === "retrieving" ? 0 : 1;

  return (
    <div className="exam-ask-progress" aria-live="polite" aria-busy="true">
      <Steps
        size="small"
        current={current}
        items={[
          { title: "检索资料", description: "在向量库中查找相关片段…" },
          { title: "生成回答", description: "根据引用组织答案，请稍候…" },
        ]}
      />
    </div>
  );
}
