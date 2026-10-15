"""Hermes adapter. Registration performs no HTTP requests."""
import json
from pathlib import Path
from .client import get_ticket

SCHEMA = {
    "name": "local_ticket_get",
    "description": "按 TASK-123 格式编号查询本地模拟工单；只读操作。",
    "parameters": {
        "type": "object",
        "properties": {"ticket_id": {"type": "string", "description": "例如 TASK-101"}},
        "required": ["ticket_id"],
        "additionalProperties": False,
    },
}


def register(ctx):
    def query(args, **kwargs):
        from agent.secret_scope import get_secret
        result = get_ticket(
            args.get("ticket_id"),
            base_url=ctx.get_config("base_url", default="http://127.0.0.1:8765"),
            timeout=ctx.get_config("timeout", default=3.0),
            token=get_secret("LOCAL_TICKET_API_KEY"),
        )
        return json.dumps(result, ensure_ascii=False)

    ctx.register_tool(name="local_ticket_get", toolset="local_tickets",
                      schema=SCHEMA, handler=query)
    ctx.register_skill("ticket-report", Path(__file__).parent / "skills/ticket-report/SKILL.md")
