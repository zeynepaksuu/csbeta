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
from app.db import get_system_stats

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
        stats = await get_system_stats()
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Total Tasks: {stats['total_tasks']}, Job Statuses: {stats['job_statuses']}"
                }
            ]
        }
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Database query error: {e}"}], "is_error": True}

agent_mcp_server = create_sdk_mcp_server(
    name="system_tools",
    version="1.0.0",
    tools=[calculate, database_stats]
)

async def run_agent(task_id: str, prompt: str, task_type: str, callback=None):
    if callback:
        await callback("agent_started", {"task_id": task_id, "prompt": prompt, "type": task_type})

    try:
        options = ClaudeAgentOptions(
            mcp_servers={"tools": agent_mcp_server},
            allowed_tools=[
                "mcp__tools__calculate",
                "mcp__tools__database_stats"
            ],
            tools=[],
            setting_sources=[],
            max_turns=8,
            system_prompt="You are an autonomous assistant. Use provided tools when needed to answer requests concisely."
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