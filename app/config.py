import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgrespassword@localhost:5433/agent_flow"
)
CENTRIFUGO_API_URL = os.getenv("CENTRIFUGO_API_URL", "http://localhost:8000/api")
CENTRIFUGO_API_KEY = os.getenv("CENTRIFUGO_API_KEY", "centrifugo_api_key")
CENTRIFUGO_WS_URL = os.getenv(
    "CENTRIFUGO_WS_URL",
    "ws://localhost:8000/connection/websocket"
)

CLAUDE_CODE_OAUTH_TOKEN = os.getenv("CLAUDE_CODE_OAUTH_TOKEN", "")
