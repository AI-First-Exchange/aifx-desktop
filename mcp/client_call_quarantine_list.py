import asyncio, os
from fastmcp import Client

async def main():
    os.environ["AIRX_INGEST_ROOT"] = os.path.expanduser("~/airx/ingest")

    async with Client("mcp/server.py") as client:
        res = await client.call_tool("airx.quarantine_list", {"limit": 10})
        print(res.data)

asyncio.run(main())
