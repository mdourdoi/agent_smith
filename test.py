# test.py
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio

async def main():
    params = StdioServerParameters(
        command="python",
        args=["mcp_tools_mbpp.py"]
    )
    
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            result = await session.call_tool("run_tests", {
                "code": "def sub_list(nums1, nums2):\n    return list(map(lambda x, y: x - y, nums1, nums2))",
                "tests": [
                    "assert sub_list([1,2],[3,4])==[-2,-2]",
                    "assert sub_list([90,120],[50,70])==[40,50]"
                ]
            })
            print(result.content[0].text)

asyncio.run(main())