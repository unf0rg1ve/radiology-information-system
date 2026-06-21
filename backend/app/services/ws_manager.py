"""
WebSocket connection manager for real-time updates.
Channels:
- worklist: updates when order/worklist status changes or studies arrive
- cito: updates when critical findings are issued
"""
import json
import logging
from typing import Dict, List
from starlette.websockets import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # channel -> list of websockets
        self._channels: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, channel: str) -> None:
        await websocket.accept()
        self._channels.setdefault(channel, []).append(websocket)
        logger.debug("WS connect channel=%s total=%d", channel, len(self._channels[channel]))

    def disconnect(self, websocket: WebSocket, channel: str) -> None:
        connections = self._channels.get(channel, [])
        if websocket in connections:
            connections.remove(websocket)
        logger.debug("WS disconnect channel=%s total=%d", channel, len(connections))

    async def broadcast(self, channel: str, message: dict) -> None:
        connections = self._channels.get(channel, [])
        if not connections:
            return
        payload = json.dumps(message, default=str)
        disconnected = []
        for connection in connections:
            try:
                await connection.send_text(payload)
            except Exception as e:
                logger.warning("WS send failed: %s", e)
                disconnected.append(connection)
        # Clean up dead connections
        for dead in disconnected:
            self.disconnect(dead, channel)


ws_manager = ConnectionManager()
