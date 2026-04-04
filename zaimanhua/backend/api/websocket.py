from __future__ import annotations

import asyncio
import queue

from fastapi import APIRouter, Depends, WebSocket
from starlette.websockets import WebSocketDisconnect

from zaimanhua.backend.api.dependencies import BackendContainer, get_ws_container

router = APIRouter()
EVENT_SUBSCRIBER_MAXSIZE = 10


async def _is_client_disconnected(websocket: WebSocket) -> bool:
    try:
        message = await asyncio.wait_for(websocket.receive(), timeout=0.05)
    except asyncio.TimeoutError:
        return False
    except (WebSocketDisconnect, RuntimeError):
        return True
    return message.get("type") == "websocket.disconnect"


@router.websocket("/ws/events")
async def events_stream(websocket: WebSocket, container: BackendContainer = Depends(get_ws_container)) -> None:
    await websocket.accept()
    subscriber: queue.Queue | None = None
    try:
        try:
            subscriber = container.event_bus.subscribe(maxsize=EVENT_SUBSCRIBER_MAXSIZE)
        except Exception:
            await websocket.close(code=1011)
            return

        while True:
            try:
                event = await asyncio.to_thread(subscriber.get, True, 1.0)
            except queue.Empty:
                if await _is_client_disconnected(websocket):
                    break
                continue
            await websocket.send_json(event)
    except WebSocketDisconnect:
        return
    finally:
        if subscriber is not None:
            container.event_bus.unsubscribe(subscriber)
