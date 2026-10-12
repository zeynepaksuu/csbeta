import logging
from datetime import datetime, timezone
import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


def _request(channel: str, event_type: str, payload: dict):
    data = {"event": event_type, "payload": payload, "timestamp": datetime.now(timezone.utc).isoformat()}
    headers = {"X-API-Key": settings.CENTRIFUGO_API_KEY, "Content-Type": "application/json"}
    return f"{settings.CENTRIFUGO_API_URL}/publish", {"channel": channel, "data": data}, headers


def _handle(channel: str, response: httpx.Response):
    response.raise_for_status()
    result = response.json()
    if "error" in result:
        logger.warning("Centrifugo publish error on %s: %s", channel, result["error"])
    return result


async def publish_event(channel: str, event_type: str, payload: dict):
    url, body, headers = _request(channel, event_type, payload)
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            return _handle(channel, await client.post(url, json=body, headers=headers))
        except Exception as e:
            logger.warning("Centrifugo publish failed on %s: %s", channel, e)
            return {"error": str(e)}


def publish_event_sync(channel: str, event_type: str, payload: dict):
    url, body, headers = _request(channel, event_type, payload)
    try:
        return _handle(channel, httpx.post(url, json=body, headers=headers, timeout=10.0))
    except Exception as e:
        logger.warning("Centrifugo publish failed on %s: %s", channel, e)
        return {"error": str(e)}
