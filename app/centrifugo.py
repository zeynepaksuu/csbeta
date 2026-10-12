import logging
import httpx
from datetime import datetime, timezone
from app.config import CENTRIFUGO_API_URL, CENTRIFUGO_API_KEY

logger = logging.getLogger(__name__)

async def publish_event(channel: str, event_type: str, payload: dict):
    data = { "event": event_type, "payload": payload, "timestamp": datetime.now(timezone.utc).isoformat()}
    headers = { "X-API-Key": CENTRIFUGO_API_KEY, "Content-Type": "application/json"}
    body = {"channel": channel, "data": data}

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(f"{CENTRIFUGO_API_URL}/publish", json=body, headers=headers)
            response.raise_for_status()
            result = response.json()
            if "error" in result:
                logger.warning("Centrifugo publish error on %s: %s", channel, result["error"])
            return result
        except Exception as e:
            logger.warning("Centrifugo publish failed on %s: %s", channel, e)
            return {"error": str(e)}
