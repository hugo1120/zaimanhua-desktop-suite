import type { BackendEvent } from "../api/contracts";

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { connectEvents } from "./events";

class MockWebSocket {
  static instances: MockWebSocket[] = [];

  onopen?: () => void;
  onmessage?: (event: { data: string }) => void;
  onclose?: () => void;
  onerror?: () => void;

  constructor(public url: string) {
    if (!url.includes("/ws/events")) {
      throw new Error(`unexpected websocket url: ${url}`);
    }
    MockWebSocket.instances.push(this);
  }

  close() {
    this.onclose?.();
  }
}

describe("connectEvents", () => {
  let originalWebSocket: typeof WebSocket;

  beforeEach(() => {
    originalWebSocket = globalThis.WebSocket;
    MockWebSocket.instances = [];
    vi.useFakeTimers();
    globalThis.WebSocket = MockWebSocket as unknown as typeof WebSocket;
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    globalThis.WebSocket = originalWebSocket;
  });

  test("reconnects after close and notifies", () => {
    const receivedEvents: BackendEvent[] = [];
    let reconnectCount = 0;

    const socket = connectEvents(
      (event) => {
        receivedEvents.push(event);
      },
      {
        onReconnect: () => {
          reconnectCount += 1;
        },
      },
    );

    expect(MockWebSocket.instances).toHaveLength(1);
    const firstSocket = MockWebSocket.instances[0];
    firstSocket.onopen?.();
    firstSocket.onmessage?.({ data: JSON.stringify({ type: "queue.changed", payload: null }) });
    expect(receivedEvents).toEqual([{ type: "queue.changed", payload: null }]);

    firstSocket.onclose?.();
    vi.runOnlyPendingTimers();

    expect(MockWebSocket.instances).toHaveLength(2);
    const secondSocket = MockWebSocket.instances[1];
    secondSocket.onopen?.();
    expect(reconnectCount).toBe(1);

    socket.close();
  });
});
