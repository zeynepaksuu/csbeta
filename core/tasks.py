import asyncio
import sys
from asgiref.sync import sync_to_async
from django.utils import timezone
from procrastinate.contrib.django import app
from core.agent import run_agent
from core.centrifugo import publish_event
from core.models import TaskResult
from core.prompts import build_system_prompt, build_user_prompt


async def run_agent_in_compatible_loop(**kwargs):
    if sys.platform != "win32":
        return await run_agent(**kwargs)

    # Procrastinate Windows'ta SelectorEventLoop kullanıyor, o da subprocess açamıyor;
    # Claude CLI'ı başlatabilmek için agent'ı ayrı thread'de ProactorEventLoop ile çalıştır.
    def runner():
        with asyncio.Runner(loop_factory=asyncio.ProactorEventLoop) as loop_runner:
            return loop_runner.run(run_agent(**kwargs))

    return await asyncio.to_thread(runner)


async def broadcast_status(task: TaskResult, **extra):
    payload = {"task_id": task.task_id, "status": task.status, **extra}
    await publish_event(channel=f"tasks:{task.task_id}", event_type="task_status", payload=payload)
    await publish_event(channel="public:stream", event_type="feed_update", payload=payload)


@app.task(queue="agents")
async def process_agent_task(task_id: str):
    task = await TaskResult.objects.select_related("company").aget(pk=task_id)

    task.status = TaskResult.Status.RUNNING
    await task.asave(update_fields=["status"])
    await broadcast_status(task, prompt=task.prompt)

    async def centrifugo_callback(step_name: str, data: dict):
        await publish_event(channel=f"tasks:{task_id}", event_type=step_name, payload=data)
        await publish_event(
            channel="public:stream",
            event_type="agent_action",
            payload={"task_id": task_id, "action": step_name, "data": data}
        )

    try:
        system_prompt = await sync_to_async(build_system_prompt)(task.company)
        user_prompt = await sync_to_async(build_user_prompt)(task)
        result = await run_agent_in_compatible_loop(
            task_id=task_id,
            prompt=user_prompt,
            system_prompt=system_prompt,
            company_name=task.company.name if task.company else None,
            callback=centrifugo_callback
        )
    except Exception as exc:
        task.status = TaskResult.Status.FAILED
        task.result = str(exc)
        task.completed_at = timezone.now()
        await task.asave(update_fields=["status", "result", "completed_at"])
        await broadcast_status(task, error=str(exc))
        raise

    task.status = TaskResult.Status.COMPLETED
    task.result = result
    task.completed_at = timezone.now()
    await task.asave(update_fields=["status", "result", "completed_at"])
    await broadcast_status(task, result=result)
