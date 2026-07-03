import type { AskResult } from "@/lib/api/types";

export type AskPhase = "retrieving" | "generating";

export interface ConversationTurn {
  id: string;
  question: string;
  result: AskResult | null;
  error: string | null;
  /** 流式生成中的累积文本 */
  streamingAnswer: string | null;
  /** 仅当前进行中的轮次有值 */
  phase: AskPhase | null;
  createdAt: number;
}

export const MAX_CONVERSATION_TURNS = 30;
