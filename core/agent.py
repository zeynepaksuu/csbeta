import logging
import re
from claude_agent_sdk import (
    tool,
    create_sdk_mcp_server,
    ClaudeAgentOptions,
    AssistantMessage,
    UserMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
    query
)
from django.conf import settings
from django.db.models import Count
from procrastinate.contrib.django.models import ProcrastinateJob
from core.models import TaskResult

logger = logging.getLogger(__name__)

@tool("calculate", "Evaluate mathematical expressions", {"expression": str})
async def calculate(args):
    expression = args.get("expression", "")
    safe_pattern = re.compile(r"^[\d\s\+\-\*\/\(\)\.\%]+$")
    if not safe_pattern.match(expression) or "**" in expression:
        return {"content": [{"type": "text", "text": "Invalid arithmetic expression."}], "is_error": True}
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return {"content": [{"type": "text", "text": f"Result: {result}"}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Calculation error: {e}"}], "is_error": True}


@tool("database_stats", "Fetch PostgreSQL task and queue metrics", {})
async def database_stats(args):
    try:
        total_tasks = await TaskResult.objects.acount()
        job_statuses = {
            row["status"]: row["count"]
            async for row in ProcrastinateJob.objects.order_by().values("status").annotate(count=Count("id"))
        }
        return {"content": [{"type": "text", "text": f"Total Tasks: {total_tasks}, Job Statuses: {job_statuses}"}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Database query error: {e}"}], "is_error": True}


agent_mcp_server = create_sdk_mcp_server(
    name="system_tools",
    version="1.0.0",
    tools=[calculate, database_stats]
)


def build_mcp_servers():
    servers = {"tools": agent_mcp_server}
    allowed = ["mcp__tools__calculate", "mcp__tools__database_stats"]
    # Token sadece ortam değişkeninden okunur; tanımlı değilse harici sunucuya bağlanılmaz.
    if settings.EXTERNAL_MCP_URL and settings.EXTERNAL_MCP_TOKEN:
        servers["external"] = {
            "type": "http",
            "url": settings.EXTERNAL_MCP_URL,
            "headers": {"Authorization": f"Bearer {settings.EXTERNAL_MCP_TOKEN}"},
        }
        allowed.append("mcp__external")
    return servers, allowed


async def run_agent(task_id: str, prompt: str, system_prompt: str, company_name: str | None = None, callback=None):
    if callback:
        await callback("agent_started", {
            "task_id": task_id,
            "prompt": prompt,
            "company": company_name,
        })

    try:
        mcp_servers, allowed_tools = build_mcp_servers()
        options = ClaudeAgentOptions(
            mcp_servers=mcp_servers,
            allowed_tools=allowed_tools,
            tools=[],
            setting_sources=[],
            max_turns=15,
            system_prompt=system_prompt
        )

        if callback:
            await callback("agent_thinking", {"task_id": task_id, "status": "running_claude_sdk"})

        final_text = ""
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        if callback:
                            await callback("agent_chunk", {"task_id": task_id, "chunk": block.text})
                    elif isinstance(block, ToolUseBlock):
                        if callback:
                            await callback("agent_tool_use", {"task_id": task_id, "tool": block.name, "input": block.input})
            elif isinstance(message, UserMessage) and isinstance(message.content, list):
                for block in message.content:
                    if isinstance(block, ToolResultBlock) and callback:
                        await callback("agent_tool_result", {"task_id": task_id, "tool_use_id": block.tool_use_id, "content": block.content, "is_error": block.is_error})
            elif isinstance(message, ResultMessage):
                if message.is_error:
                    raise RuntimeError(f"Claude run failed: {message.subtype} {message.errors or message.result}")
                final_text = message.result or ""
                if callback:
                    await callback("agent_usage", {
                        "task_id": task_id,
                        "num_turns": message.num_turns,
                        "duration_ms": message.duration_ms,
                        "total_cost_usd": message.total_cost_usd,
                    })

        if not final_text:
            final_text = "Task executed successfully by Claude Agent."

        if callback:
            await callback("agent_completed", {"task_id": task_id, "result": final_text})

        return final_text

    except Exception as e:
        logger.exception("Claude Agent SDK execution failed")
        if callback:
            await callback("agent_completed", {"task_id": task_id, "result": f"Error: {e}"})
        raise
