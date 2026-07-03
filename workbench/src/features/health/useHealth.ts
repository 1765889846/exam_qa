import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";
import { isAbortError } from "@/lib/api/errors";
import type { HealthData } from "@/lib/api/types";

const POLL_MS = 30_000;

export function useHealth() {
  const [data, setData] = useState<HealthData | null>(null);
  const [error, setError] = useState(false);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    try {
      const result = await apiClient.get<HealthData>("/health", { signal });
      setData(result);
      setError(false);
    } catch (e) {
      if (signal?.aborted || isAbortError(e)) {
        return;
      }
      setError(true);
    }
  }, []);

  useEffect(() => {
    const ac = new AbortController();
    refresh(ac.signal);
    const id = window.setInterval(() => refresh(), POLL_MS);
    return () => {
      ac.abort();
      window.clearInterval(id);
    };
  }, [refresh]);

  return { data, error, refresh };
}
