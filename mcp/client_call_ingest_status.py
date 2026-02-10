import asyncio, os
from fastmcp import Client

async def main():
    # Force env for the spawned MCP server subprocess
    os.environ["AIRX_INGEST_ROOT"] = os.path.expanduser("~/airx/ingest")
    os.environ["AIRX_NOWPLAYING_PATH"] = os.path.expanduser("~/airx/nowplaying.json")

    async with Client("mcp/server.py") as client:
        res = await client.call_tool("airx.ingest_status", {})
        # Print clean JSON only (easier to read)
        print(res.data)

asyncio.run(main())
