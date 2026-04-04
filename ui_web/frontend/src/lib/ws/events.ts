import type { BackendEvent } from "../api/contracts";
import { resolveWebSocketUrl } from "../backend-origin";

const RECONNECT_DELAY = 2000;

export interface EventSocketLike {
  close(): void;
}

interface EventStreamSocket extends EventSocketLike {
  onopen: (() => void) | null;
  onmessage: ((event: { data: string }) => void) | null;
  onclose: (() => void) | null;
  onerror?: (() => void) | null;
}

export interface ConnectEventsOptions {
  onReconnect?(): void;
  reconnectDelayMs?: number;
  createSocket?(url: string): EventStreamSocket;
}

export function connectEvents(
  onEvent: (event: BackendEvent) => void,
  options: ConnectEventsOptions = {},
): EventSocketLike {
  const reconnectDelayMs = options.reconnectDelayMs ?? RECONNECT_DELAY;
  const createSocket =
    options.createSocket ?? ((url: string) => new WebSocket(url) as unknown as EventStreamSocket);

  let socket: EventStreamSocket | null = null;
  let shouldReconnect = true;
  let reconnectTimer: any = null;
  let connectAttempt = 0;

  const scheduleReconnect = () => {
    if (!shouldReconnect || reconnectTimer !== null) {
      return;
    }

    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, reconnectDelayMs);
  };

  const connect = () => {
    connectAttempt += 1;
    socket = createSocket(resolveWebSocketUrl());

    socket.onopen = () => {
      if (connectAttempt > 1) {
        options.onReconnect?.();
      }
    };

    socket.onmessage = (message) => {
      try {
        const parsed = JSON.parse(message.data);
        if (parsed && typeof parsed === "object" && typeof parsed.type === "string") {
          onEvent(parsed as BackendEvent);
        }
      } catch {
        // ignore malformed messages
      }
    };

    socket.onclose = () => {
      socket = null;
      if (shouldReconnect) {
        scheduleReconnect();
      }
    };

    socket.onerror = () => {
      socket?.close();
    };
  };

  connect();

  return {
    close() {
      shouldReconnect = false;
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      socket?.close();
      socket = null;
    },
  };
}
