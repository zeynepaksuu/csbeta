from app.db import procrastinate_app, save_task_result
from app.centrifugo import publish_event
from app.agent import run_agent

@procrastinate_app.task(queue="agents")
async def process_agent_task(task_id: str, prompt: str, task_type: str):
    await save_task_result(task_id=task_id, prompt=prompt, task_type=task_type, status="running")
    
    await publish_event(
        channel=f"tasks:{task_id}",
        event_type="task_status",
        payload={"task_id": task_id, "status": "running"}
    )
    await publish_event(
        channel="public:stream",
        event_type="feed_update",
        payload={"task_id": task_id, "status": "running", "prompt": prompt}
    )

    async def centrifugo_callback(step_name: str, data: dict):
        await publish_event(
            channel=f"tasks:{task_id}",
            event_type=step_name,
            payload=data
        )
        await publish_event(
            channel="public:stream",
            event_type="agent_action",
            payload={"task_id": task_id, "action": step_name, "data": data}
        )

    try:
        result = await run_agent(
            task_id=task_id,
            prompt=prompt,
            task_type=task_type,
            callback=centrifugo_callback
        )
        await save_task_result(
            task_id=task_id,
            prompt=prompt,
            task_type=task_type,
            status="completed",
            result=result
        )
        await publish_event(
            channel=f"tasks:{task_id}",
            event_type="task_status",
            payload={"task_id": task_id, "status": "completed", "result": result}
        )
        await publish_event(
            channel="public:stream",
            event_type="feed_update",
            payload={"task_id": task_id, "status": "completed", "result": result}
        )
    except Exception as exc:
        await save_task_result(
            task_id=task_id,
            prompt=prompt,
            task_type=task_type,
            status="failed",
            result=str(exc)
        )
        await publish_event(
            channel=f"tasks:{task_id}",
            event_type="task_status",
            payload={"task_id": task_id, "status": "failed", "error": str(exc)}
        )
        await publish_event(
            channel="public:stream",
            event_type="feed_update",
            payload={"task_id": task_id, "status": "failed", "error": str(exc)}
        )
        raise
