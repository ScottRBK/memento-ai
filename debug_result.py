"""Debug script to see actual result structure"""
import asyncio
from fastmcp import Client

async def main():
    async with Client("http://localhost:8020/mcp") as client:
        result = await client.call_tool("get_current_user", {})

        print("Result type:", type(result))
        print("Result.data type:", type(result.data))
        print("Result.data dir:", [x for x in dir(result.data) if not x.startswith('_')])
        print("\nTrying to print result.data:")
        print(result.data)
        print("\nRepr:")
        print(repr(result.data))

if __name__ == "__main__":
    asyncio.run(main())
