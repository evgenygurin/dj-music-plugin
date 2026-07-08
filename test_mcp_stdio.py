#!/usr/bin/env python3
"""Debug MCP server via stdio."""
import asyncio
import json
import os

ENV = {
    **os.environ,
    "DJ_DATABASE_URL": "postgresql+asyncpg://postgres.bowosphlnghhgaulcyfm:bJ2QjBfy7qQqJxd7@aws-1-eu-central-1.pooler.supabase.com:5432/postgres",
    "DJ_YM_TOKEN": "y0__xCrh9J3GN74BiDBy870FUAInK8m58f2fxS2a172G-rjVrpm",
    "DJ_MCP_DEBUG": "1",
}

async def test():
    print("Starting MCP server...")
    proc = await asyncio.create_subprocess_exec(
        "/Users/laptop/dev/dj-music-plugin/.venv/bin/python",
        "-m", "fastmcp",
        "run", "fastmcp.json", "--no-banner",
        env=ENV,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd="/Users/laptop/dev/dj-music-plugin",
    )

    # Wait for server to start fully
    await asyncio.sleep(2)

    # Send initialize request
    init_req = json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}
    }) + "\n"
    print(">>> initialize")
    proc.stdin.write(init_req.encode())
    await proc.stdin.drain()

    # Read response
    resp = await asyncio.wait_for(proc.stdout.readline(), timeout=10.0)
    print(f"<<< {resp.decode().strip()[:300]}")

    # Send initialized notification
    notif = json.dumps({
        "jsonrpc": "2.0",
        "method": "notifications/initialized"
    }) + "\n"
    proc.stdin.write(notif.encode())
    await proc.stdin.drain()

    # Request tool list
    list_req = json.dumps({
        "jsonrpc": "2.0", "id": 2,
        "method": "tools/list"
    }) + "\n"
    print(">>> tools/list")
    proc.stdin.write(list_req.encode())
    await proc.stdin.drain()

    resp = await asyncio.wait_for(proc.stdout.readline(), timeout=10.0)
    print(f"<<< tools/list response: {resp.decode().strip()[:500]}")

    # Dump stderr
    try:
        stderr_data = await asyncio.wait_for(proc.stderr.read(4096), timeout=2.0)
        if stderr_data:
            print(f"STDERR: {stderr_data.decode()[:500]}")
    except:
        pass

    proc.terminate()
    await proc.wait()
    print("Server terminated cleanly")

if __name__ == "__main__":
    asyncio.run(test())
