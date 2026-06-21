"""
WebSocket endpoint for real-time updates (F4.2, F5.6).
Channels:
- worklist: status changes, new studies, unmatched studies
- cito: new critical findings

Connection: ws://host/api/ws?token=<jwt>&channel=<worklist|cito>
"""
import logging
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt
from app.core.config import get_settings
from app.services.ws_manager import ws_manager

settings = get_settings()

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ws", tags=["WebSocket"])

ALLOWED_CHANNELS = {"worklist", "cito"}


@router.websocket("")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    channel: str = Query(...),
):
    """Authenticated WebSocket connection for real-time updates."""
    if channel not in ALLOWED_CHANNELS:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await ws_manager.connect(websocket, channel)
    try:
        while True:
            # Keep connection alive, ignore client messages
            data = await websocket.receive_text()
            logger.debug("WS message from %s: %s", payload.get("login"), data)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, channel)
    except Exception as e:
        logger.warning("WS error: %s", e)
        ws_manager.disconnect(websocket, channel)
    except Exception as e:
        logger.warning("WS error: %s", e)
        ws_manager.disconnect(websocket, channel)
