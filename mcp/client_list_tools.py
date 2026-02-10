import asyncio
from fastmcp import Client

async def main():
    client = Client("mcp/server.py")  # <- stdio inferred from file path
    async with client:
        tools = await client.list_tools()
        for t in tools:
            print(t.name)

asyncio.run(main())
