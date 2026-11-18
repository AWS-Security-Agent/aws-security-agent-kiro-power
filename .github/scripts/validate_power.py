#!/usr/bin/env python3
"""Validate the Kiro Power and smoke-test the MCP server it launches.

Checks:
  1. mcp.json is valid JSON with the expected "security-agent" stdio server.
  2. POWER.md has YAML frontmatter with the fields Kiro reads.
  3. The server starts exactly as mcp.json launches it, completes an MCP
     initialize handshake over stdio, and exposes every tool that POWER.md
     documents in its "Tools Available" table.

Standard library only, so the check itself has no dependencies to bump.
"""

import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER_NAME = "security-agent"
REQUIRED_FRONTMATTER = ("name", "displayName", "description", "keywords")
TIMEOUT_SECONDS = 180  # first run includes `uvx` resolving and installing the package


def fail(message: str) -> None:
    print(f"::error::{message}")
    sys.exit(1)


def load_server_config() -> dict:
    try:
        config = json.loads((ROOT / "mcp.json").read_text())
    except json.JSONDecodeError as err:
        fail(f"mcp.json is not valid JSON: {err}")
    server = config.get("mcpServers", {}).get(SERVER_NAME)
    if not isinstance(server, dict):
        fail(f'mcp.json must define mcpServers["{SERVER_NAME}"]')
    if not isinstance(server.get("command"), str) or not server["command"]:
        fail(f"mcpServers.{SERVER_NAME}.command must be a non-empty string")
    args = server.get("args", [])
    if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        fail(f"mcpServers.{SERVER_NAME}.args must be a list of strings")
    print(f"mcp.json OK: {server['command']} {' '.join(args)}")
    return server


def documented_tools() -> set[str]:
    text = (ROOT / "POWER.md").read_text()
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        fail("POWER.md must start with a --- frontmatter block")
    keys = {line.split(":", 1)[0].strip() for line in match.group(1).splitlines() if ":" in line}
    missing = [k for k in REQUIRED_FRONTMATTER if k not in keys]
    if missing:
        fail(f"POWER.md frontmatter is missing: {', '.join(missing)}")
    section = text.split("## Tools Available", 1)
    if len(section) != 2:
        fail('POWER.md has no "## Tools Available" section')
    table = section[1].split("\n## ", 1)[0]
    tools = set(re.findall(r"^\|\s*`([a-z_]+)`\s*\|", table, re.M))
    if not tools:
        fail('No tools found in the POWER.md "Tools Available" table')
    print(f"POWER.md OK: {len(tools)} documented tools")
    return tools


def served_tools(server: dict) -> set[str]:
    # The server must start without AWS credentials; tools/list is offline.
    env = {k: v for k, v in os.environ.items() if not k.startswith("AWS_")}
    env.update(server.get("env", {}))
    env.setdefault("AWS_REGION", "us-east-1")
    proc = subprocess.Popen(
        [server["command"], *server.get("args", [])],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        text=True,
        env=env,
    )
    timer = threading.Timer(TIMEOUT_SECONDS, proc.kill)
    timer.start()

    def send(message: dict) -> None:
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()

    def receive(request_id: int) -> dict:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            message = json.loads(line)
            if message.get("id") == request_id:
                if "error" in message:
                    fail(f"MCP request {request_id} failed: {message['error']}")
                return message["result"]
        fail(f"MCP server exited or timed out before answering request {request_id}")

    try:
        send({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "power-ci", "version": "1"},
            },
        })
        info = receive(1).get("serverInfo", {})
        print(f"initialize OK: {info.get('name')} {info.get('version')}")
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        return {tool["name"] for tool in receive(2).get("tools", [])}
    finally:
        timer.cancel()
        proc.kill()
        proc.wait()


def main() -> None:
    server = load_server_config()
    expected = documented_tools()
    actual = served_tools(server)
    print(f"Server tools: {', '.join(sorted(actual))}")
    missing = expected - actual
    if missing:
        fail(f"POWER.md documents tools the server does not expose: {', '.join(sorted(missing))}")
    undocumented = actual - expected
    if undocumented:
        print(f"::warning::Server exposes tools not documented in POWER.md: {', '.join(sorted(undocumented))}")
    print("Power validation passed")


if __name__ == "__main__":
    main()
