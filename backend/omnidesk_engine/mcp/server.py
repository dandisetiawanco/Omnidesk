from __future__ import annotations

from typing import Any

from omnidesk_engine.automation import capabilities, filesystem
from omnidesk_engine.db import Database
from omnidesk_engine.security.credentials import CredentialVault
from omnidesk_engine.security.policy import TOOL_POLICIES


def list_mcp_tools() -> list[dict[str, Any]]:
    return [
        {
            "name": policy.tool,
            "description": policy.description,
            "risk": policy.risk.value,
            "requires_approval": policy.requires_approval,
            "reversible": policy.reversible,
        }
        for policy in TOOL_POLICIES.values()
    ]


async def handle_mcp_rpc(
    payload: dict[str, Any],
    db: Database,
    vault: CredentialVault,
) -> dict[str, Any]:
    rpc_id = payload.get("id")
    method = payload.get("method")
    params = payload.get("params") or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "omnidesk-mcp", "version": "0.1.0"},
                "capabilities": {"tools": {"listChanged": False}},
            },
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {"tools": list_mcp_tools()},
        }

    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}
        if tool_name == "system.capabilities":
            profile = capabilities.collect_system_profile(vault)
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {"content": [{"type": "json", "json": profile.model_dump()}]},
            }
        if tool_name == "filesystem.inspect_directory":
            settings = db.get_settings()
            roots = settings.scoped_directories or None
            result = filesystem.inspect_directory(arguments["directory"], allowed_roots=roots)
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {"content": [{"type": "json", "json": result}]},
            }
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "error": {
                "code": -32001,
                "message": (
                    f"Tool '{tool_name}' requires interactive human approval in OmniDesk UI "
                    "and cannot run headlessly over MCP."
                ),
            },
        }

    return {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "error": {"code": -32601, "message": f"Unknown MCP method '{method}'."},
    }
