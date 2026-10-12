import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from pydantic import BaseModel
from app.config import CENTRIFUGO_WS_URL
from app.db import (
    init_db,
    procrastinate_app,
    save_task_result,
    get_task_result,
    get_db_jobs,
    get_system_stats
)
from app.tasks import process_agent_task
from app.centrifugo import publish_event

class CreateTaskRequest(BaseModel):
    prompt: str
    task_type: str = "general"

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with procrastinate_app.open_async():
        yield

app = FastAPI(title="AgentFlow", lifespan=lifespan)

templates_path = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_path))

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"centrifugo_ws_url": CENTRIFUGO_WS_URL}
    )

@app.post("/api/tasks")
async def create_task(payload: CreateTaskRequest):
    task_id = uuid.uuid4().hex[:10]
    await save_task_result(
        task_id=task_id,
        prompt=payload.prompt,
        task_type=payload.task_type,
        status="queued"
    )
    
    await process_agent_task.defer_async(
        task_id=task_id,
        prompt=payload.prompt,
        task_type=payload.task_type
    )

    await publish_event(
        channel=f"tasks:{task_id}",
        event_type="task_queued",
        payload={"task_id": task_id, "status": "queued", "prompt": payload.prompt}
    )
    await publish_event(
        channel="public:stream",
        event_type="feed_update",
        payload={"task_id": task_id, "status": "queued", "prompt": payload.prompt}
    )

    return {"task_id": task_id, "status": "queued"}

@app.get("/api/tasks/{task_id}")
async def fetch_task(task_id: str):
    record = await get_task_result(task_id)
    if not record:
        raise HTTPException(status_code=404, detail="Task not found")
    return record

@app.get("/api/jobs")
async def fetch_jobs():
    jobs = await get_db_jobs(limit=25)
    return {"jobs": jobs}

@app.get("/api/stats")
async def fetch_stats():
    stats = await get_system_stats()
    return stats
