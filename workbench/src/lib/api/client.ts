import {
  ApiError,
  isAbortError,
  parseJsonObject,
  unwrapResponse,
} from "./errors";
import type { ApiResponse } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";
const REQUEST_TIMEOUT_MS = 15_000;

export type ApiRequestOptions = {
  signal?: AbortSignal;
};

function mergeSignal(
  userSignal: AbortSignal | undefined,
  timeoutMs: number,
): { signal: AbortSignal; cleanup: () => void } {
  const timeout = AbortSignal.timeout(timeoutMs);
  if (!userSignal) {
    return { signal: timeout, cleanup: () => {} };
  }
  const ac = new AbortController();
  const onAbort = () => ac.abort(userSignal.reason ?? timeout.reason);
  userSignal.addEventListener("abort", onAbort, { once: true });
  timeout.addEventListener("abort", onAbort, { once: true });
  return {
    signal: ac.signal,
    cleanup: () => {
      userSignal.removeEventListener("abort", onAbort);
      timeout.removeEventListener("abort", onAbort);
    },
  };
}

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const { signal, cleanup } = mergeSignal(init?.signal ?? undefined, REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE}${path}`, { ...init, signal });
    const body = await parseJsonObject<T>(response);

    if (!response.ok) {
      const message =
        "message" in body && body.message
          ? body.message
          : `请求失败 (HTTP ${response.status})`;
      throw new ApiError(response.status, message, body.code);
    }

    return unwrapResponse(body as ApiResponse<T>);
  } catch (error) {
    if (init?.signal?.aborted || isAbortError(error)) {
      throw error;
    }
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof DOMException && error.name === "TimeoutError") {
      throw new ApiError(0, "请求超时，请确认后端已启动");
    }
    throw new ApiError(
      0,
      error instanceof Error ? error.message : "网络请求失败",
    );
  } finally {
    cleanup();
  }
}

export const apiClient = {
  get<T>(path: string, options?: ApiRequestOptions): Promise<T> {
    return request<T>(path, { signal: options?.signal });
  },

  post<T>(
    path: string,
    body?: unknown,
    options?: ApiRequestOptions,
  ): Promise<T> {
    const init: RequestInit = { method: "POST", signal: options?.signal };
    if (body !== undefined) {
      init.headers = { "Content-Type": "application/json" };
      init.body = JSON.stringify(body);
    }
    return request<T>(path, init);
  },

  postForm<T>(path: string, form: FormData, options?: ApiRequestOptions): Promise<T> {
    return request<T>(path, {
      method: "POST",
      body: form,
      signal: options?.signal,
    });
  },

  delete<T>(path: string, options?: ApiRequestOptions): Promise<T> {
    return request<T>(path, { method: "DELETE", signal: options?.signal });
  },

  patch<T>(
    path: string,
    body?: unknown,
    options?: ApiRequestOptions,
  ): Promise<T> {
    const init: RequestInit = { method: "PATCH", signal: options?.signal };
    if (body !== undefined) {
      init.headers = { "Content-Type": "application/json" };
      init.body = JSON.stringify(body);
    }
    return request<T>(path, init);
  },
};

export { API_BASE };
