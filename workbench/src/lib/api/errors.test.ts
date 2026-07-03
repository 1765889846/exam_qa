import { describe, expect, it } from "vitest";
import { ApiError, parseJsonObject, unwrapResponse } from "./errors";

describe("ApiError", () => {
  it("sets status, code, and message", () => {
    const error = new ApiError(404, "not found", 404);
    expect(error.name).toBe("ApiError");
    expect(error.message).toBe("not found");
    expect(error.status).toBe(404);
    expect(error.code).toBe(404);
  });
});

describe("unwrapResponse", () => {
  it("returns data from success envelope", () => {
    expect(unwrapResponse({ code: 200, data: { id: 1 } })).toEqual({ id: 1 });
  });

  it("throws ApiError on error envelope", () => {
    expect(() => unwrapResponse({ code: 400, message: "bad request" })).toThrow(
      ApiError,
    );
    try {
      unwrapResponse({ code: 400, message: "bad request" });
    } catch (e) {
      expect(e).toMatchObject({ message: "bad request", code: 400 });
    }
  });
});

describe("parseJsonObject", () => {
  it("throws ApiError when body is not JSON", async () => {
    const response = new Response("<html>bad gateway</html>", { status: 502 });
    await expect(parseJsonObject(response)).rejects.toMatchObject({
      status: 502,
      message: "响应不是 JSON (HTTP 502)",
    });
  });
});
