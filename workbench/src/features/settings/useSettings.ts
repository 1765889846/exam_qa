import { useCallback, useEffect, useState } from "react";
import { message } from "antd";
import { apiClient } from "@/lib/api/client";
import { ApiError, isAbortError } from "@/lib/api/errors";
import type { AppConfigData, ConfigUpdateRequest } from "@/lib/api/types";

function formatSaveMessage(data: AppConfigData): string {
  const fx = data.settings_effects;
  if (!fx) return "配置已保存";
  if (fx.restart_required.length > 0) {
    return `已保存；${fx.restart_required.join("、")} 需重启 uv run exam`;
  }
  if (fx.hot_reload.length > 0) {
    return `已保存，${fx.hot_reload.join("、")} 将在下次请求生效`;
  }
  return "配置已保存";
}

export function useSettings() {
  const [config, setConfig] = useState<AppConfigData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    try {
      const data = await apiClient.get<AppConfigData>("/config", { signal });
      setConfig(data);
      setError(null);
    } catch (e) {
      if (signal?.aborted || isAbortError(e)) {
        return;
      }
      setError(e instanceof ApiError ? e.message : "加载配置失败");
    } finally {
      setLoading(false);
    }
  }, []);

  const save = useCallback(async (patch: ConfigUpdateRequest) => {
    setSaving(true);
    try {
      const data = await apiClient.patch<AppConfigData>("/config", patch);
      setConfig(data);
      message.success(formatSaveMessage(data));
      return data;
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "保存失败";
      message.error(msg);
      throw e;
    } finally {
      setSaving(false);
    }
  }, []);

  useEffect(() => {
    const ac = new AbortController();
    load(ac.signal);
    return () => ac.abort();
  }, [load]);

  return { config, loading, saving, error, reload: load, save };
};
