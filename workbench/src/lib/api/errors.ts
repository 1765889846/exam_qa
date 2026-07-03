import type { ApiErrorBody, ApiResponse } from "./types";

export class ApiError extends Error {
  status: number;
  code: number;

  constructor(status: number, message: string, code = status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export function unwrapResponse<T>(body: ApiResponse<T> | ApiErrorBody): T {
  if ("data" in body && body.data !== undefined) {
    return body.data as T;
  }
  const err = body as ApiErrorBody;
  throw new ApiError(err.code ?? 500, err.message ?? "请求失败");
}

export async function parseJsonObject<T>(
  response: Response,
): Promise<ApiResponse<T> | ApiErrorBody> {
  try {
    return (await response.json()) as ApiResponse<T> | ApiErrorBody;
  } catch {
    throw new ApiError(
      response.status,
      `响应不是 JSON (HTTP ${response.status})`,
    );
  }
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}
