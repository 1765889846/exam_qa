import { Tooltip } from "antd";
import { formatHealthComponent } from "@/lib/format";
import { useHealth } from "./useHealth";

function statusClass(status: string | undefined, error: boolean): string {
  if (error) return "exam-health-badge--err";
  if (status === "healthy") return "exam-health-badge--ok";
  if (status === "degraded") return "exam-health-badge--warn";
  return "exam-health-badge--err";
}

function statusLabel(status: string | undefined, error: boolean): string {
  if (error) return "● 连接失败";
  if (status === "healthy") return "● 服务正常";
  if (status === "degraded") return "● 部分就绪";
  if (status) return `● ${status}`;
  return "● 检查中…";
}

function healthTooltip(data: ReturnType<typeof useHealth>["data"]): string | null {
  if (!data || data.status === "healthy") return null;
  return [
    `ChromaDB: ${formatHealthComponent(data.chromadb)}`,
    `SQLite: ${formatHealthComponent(data.sqlite)}`,
    `Embedding: ${formatHealthComponent(data.embedding)}`,
    `LLM: ${formatHealthComponent(data.llm)}`,
  ].join("\n");
}

export function HealthBadge() {
  const { data, error } = useHealth();
  const tip = healthTooltip(data);

  const badge = (
    <span
      className={`exam-health-badge ${statusClass(data?.status, error)}`}
      aria-live="polite"
    >
      {statusLabel(data?.status, error)}
    </span>
  );

  if (!tip) return badge;

  return (
    <Tooltip title={<pre style={{ margin: 0, fontSize: 12 }}>{tip}</pre>}>
      {badge}
    </Tooltip>
  );
}
