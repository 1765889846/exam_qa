import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "./client";
import { ApiError } from "./errors";

describe("apiClient", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("unwraps success envelope", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ code: 200, data: { ok: true } }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(apiClient.get("/health")).resolves.toEqual({ ok: true });
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/health",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("throws ApiError on HTTP error with message", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ code: 400, message: "bad request" }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(apiClient.get("/documents")).rejects.toMatchObject({
      message: "bad request",
      status: 400,
    });
  });

  it("throws ApiError when response body is not JSON", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response("Service Unavailable", { status: 503 }),
    );

    await expect(apiClient.get("/health")).rejects.toBeInstanceOf(ApiError);
    await expect(apiClient.get("/health")).rejects.toMatchObject({
      status: 503,
      message: "响应不是 JSON (HTTP 503)",
    });
  });
});
