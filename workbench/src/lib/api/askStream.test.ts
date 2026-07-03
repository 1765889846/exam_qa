import { describe, expect, it, vi } from "vitest";
import {
  consumeAskStream,
  extractSseEvents,
  flushSseBuffer,
  parseSseEventBlock,
} from "./askStream";
import { ApiError } from "./errors";

describe("parseSseEventBlock", () => {
  it("parses data line", () => {
    const event = parseSseEventBlock('data: {"type":"phase","phase":"retrieving"}');
    expect(event).toEqual({ type: "phase", phase: "retrieving" });
  });

  it("returns null for empty block", () => {
    expect(parseSseEventBlock("")).toBeNull();
  });
});

describe("extractSseEvents", () => {
  it("splits complete events and keeps remainder", () => {
    const raw =
      'data: {"type":"delta","text":"a"}\n\n' +
      'data: {"type":"delta","text":"b"}\n\n' +
      'data: {"type":"done","data":{"answer":"ab","citations":[],"grounded":true}}';
    const { events, remainder } = extractSseEvents(raw);
    expect(events).toHaveLength(2);
    expect(events[0].type).toBe("delta");
    expect(remainder).toContain('"done"');
  });
});

describe("flushSseBuffer", () => {
  it("parses trailing event without double newline", () => {
    const trailing =
      'data: {"type":"done","data":{"answer":"ok","citations":[],"grounded":true}}';
    const events = flushSseBuffer(trailing);
    expect(events).toHaveLength(1);
    expect(events[0].type).toBe("done");
  });
});

describe("consumeAskStream", () => {
  it("throws on error event", async () => {
    const body = 'data: {"type":"error","message":"boom"}\n\n';
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          new ReadableStream({
            start(controller) {
              controller.enqueue(new TextEncoder().encode(body));
              controller.close();
            },
          }),
          { status: 200 },
        ),
      ),
    );

    await expect(
      consumeAskStream({
        question: "q",
        onEvent: () => {},
      }),
    ).rejects.toMatchObject({ message: "boom" });

    vi.unstubAllGlobals();
  });

  it("flushes final done without trailing newline", async () => {
    const donePayload = {
      type: "done",
      data: { answer: "完整", citations: [], grounded: true },
    };
    const body = `data: ${JSON.stringify(donePayload)}`;
    const events: string[] = [];

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          new ReadableStream({
            start(controller) {
              controller.enqueue(new TextEncoder().encode(body));
              controller.close();
            },
          }),
          { status: 200 },
        ),
      ),
    );

    await consumeAskStream({
      question: "q",
      onEvent: (e) => events.push(e.type),
    });

    expect(events).toContain("done");
    vi.unstubAllGlobals();
  });

  it("throws when stream ends without done", async () => {
    const body = 'data: {"type":"delta","text":"x"}\n\n';
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          new ReadableStream({
            start(controller) {
              controller.enqueue(new TextEncoder().encode(body));
              controller.close();
            },
          }),
          { status: 200 },
        ),
      ),
    );

    await expect(
      consumeAskStream({
        question: "q",
        onEvent: () => {},
      }),
    ).rejects.toBeInstanceOf(ApiError);

    vi.unstubAllGlobals();
  });
});
