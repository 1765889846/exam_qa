import { API_BASE } from "./client";
import { ApiError } from "./errors";
import type { AskResult } from "./types";

export type AskStreamEvent =
  | { type: "phase"; phase: "retrieving" | "generating" }
  | { type: "delta"; text: string }
  | { type: "done"; data: AskResult }
  | { type: "error"; message: string };

export interface AskStreamOptions {
  question: string;
  mode?: "qa";
  signal?: AbortSignal;
  onEvent: (event: AskStreamEvent) => void;
}

/** 从单个 SSE 块解析事件（不含末尾空行）。 */
export function parseSseEventBlock(block: string): AskStreamEvent | null {
  const trimmed = block.trim();
  if (!trimmed) return null;
  const line = trimmed.split("\n").find((l) => l.startsWith("data: "));
  if (!line) return null;
  return JSON.parse(line.slice(6)) as AskStreamEvent;
}

/** 从 buffer 提取完整 SSE 事件，返回剩余未闭合片段。 */
export function extractSseEvents(buffer: string): {
  events: AskStreamEvent[];
  remainder: string;
} {
  const chunks = buffer.split("\n\n");
  const remainder = chunks.pop() ?? "";
  const events: AskStreamEvent[] = [];
  for (const chunk of chunks) {
    const event = parseSseEventBlock(chunk);
    if (event) events.push(event);
  }
  return { events, remainder };
}

/** 流结束时 flush 剩余 buffer（可能没有尾随 \\n\\n）。 */
export function flushSseBuffer(buffer: string): AskStreamEvent[] {
  const trimmed = buffer.trim();
  if (!trimmed) return [];
  const event = parseSseEventBlock(trimmed);
  return event ? [event] : [];
}

async function parseErrorBody(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (body && typeof body.message === "string") {
      return body.message;
    }
  } catch {
    // ignore
  }
  return `请求失败 (HTTP ${response.status})`;
}

function dispatchEvent(
  event: AskStreamEvent,
  onEvent: (event: AskStreamEvent) => void,
  state: { gotDone: boolean },
): void {
  onEvent(event);
  if (event.type === "error") {
    throw new ApiError(502, event.message);
  }
  if (event.type === "done") {
    state.gotDone = true;
  }
}

/** 消费 POST /api/v1/ask SSE 事件流。 */
export async function consumeAskStream({
  question,
  mode = "qa",
  signal,
  onEvent,
}: AskStreamOptions): Promise<void> {
  const response = await fetch(`${API_BASE}/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({ question, mode, stream: true }),
    signal,
  });

  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorBody(response));
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new ApiError(502, "流式响应不可用");
  }

  const decoder = new TextDecoder();
  let buffer = "";
  const state = { gotDone: false };

  const processBuffer = (chunk: string) => {
    buffer += chunk;
    const parsed = extractSseEvents(buffer);
    buffer = parsed.remainder;
    for (const event of parsed.events) {
      dispatchEvent(event, onEvent, state);
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (value) {
      processBuffer(decoder.decode(value, { stream: true }));
    }
    if (done) {
      processBuffer(decoder.decode());
      for (const event of flushSseBuffer(buffer)) {
        dispatchEvent(event, onEvent, state);
      }
      break;
    }
  }

  if (!state.gotDone) {
    throw new ApiError(502, "流式响应未完成");
  }
}
