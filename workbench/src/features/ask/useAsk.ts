import { useCallback, useState } from "react";
import { message } from "antd";
import { consumeAskStream } from "@/lib/api/askStream";
import { ApiError } from "@/lib/api/errors";
import type { AskResult } from "@/lib/api/types";
import {
  MAX_CONVERSATION_TURNS,
  type AskPhase,
  type ConversationTurn,
} from "./types";

function newTurnId(): string {
  return crypto.randomUUID();
}

export function useAsk() {
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [loading, setLoading] = useState(false);

  const updateLastTurn = useCallback((patch: Partial<ConversationTurn>) => {
    setTurns((prev) => {
      if (prev.length === 0) return prev;
      const next = [...prev];
      const last = next[next.length - 1];
      next[next.length - 1] = { ...last, ...patch };
      return next;
    });
  }, []);

  const clearTurns = useCallback(() => {
    setTurns([]);
    setLoading(false);
  }, []);

  const ask = useCallback(
    async (question: string) => {
      const turnId = newTurnId();
      const newTurn: ConversationTurn = {
        id: turnId,
        question,
        result: null,
        error: null,
        streamingAnswer: null,
        phase: "retrieving",
        createdAt: Date.now(),
      };

      setTurns((prev) => {
        const next = [...prev, newTurn];
        return next.length > MAX_CONVERSATION_TURNS
          ? next.slice(-MAX_CONVERSATION_TURNS)
          : next;
      });
      setLoading(true);

      let streamed = "";

      try {
        await consumeAskStream({
          question,
          onEvent: (event) => {
            if (event.type === "phase") {
              updateLastTurn({ phase: event.phase });
              return;
            }
            if (event.type === "delta") {
              streamed += event.text;
              updateLastTurn({
                phase: "generating",
                streamingAnswer: streamed,
              });
              return;
            }
            if (event.type === "done") {
              const data = event.data as AskResult;
              updateLastTurn({
                result: data,
                error: null,
                phase: null,
                streamingAnswer: null,
              });
              if (!data.grounded) {
                message.info("未在资料中找到足够依据，请换种问法或补充资料");
              }
            }
          },
        });
      } catch (e) {
        const msg =
          e instanceof ApiError
            ? e.message
            : e instanceof Error
              ? e.message
              : "请求失败";
        message.error(msg);
        updateLastTurn({
          error: msg,
          phase: null,
          streamingAnswer: null,
        });
      } finally {
        setLoading(false);
      }
    },
    [updateLastTurn],
  );

  const activePhase: AskPhase | null = loading
    ? (turns[turns.length - 1]?.phase ?? "retrieving")
    : null;

  return { turns, loading, activePhase, ask, clearTurns };
}
