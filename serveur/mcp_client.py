# mcp_client_bridge.py
import asyncio
import threading
from typing import Dict, Any, List
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client


class MCPClientBridge:
    def __init__(self):
        self.session: ClientSession | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self.tools_metadata: List[Any] = []
        self._ctx = None
        self._ensure_event_loop()

    def _ensure_event_loop(self):
        if self._loop is None or not self._loop.is_running():
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(
                target=self._run_event_loop,
                daemon=True,
            )
            self._thread.start()

    def _run_event_loop(self):
        assert self._loop is not None
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def connect_stdio(self, server_script: str):
        self._ensure_event_loop()
        assert self._loop is not None
        server_params = StdioServerParameters(
            command="uv",
            args=["run", "python", server_script],
        )
        asyncio.run_coroutine_threadsafe(
            self._init_stdio(server_params), self._loop,
        ).result()

    def connect_http(self, url: str):
        self._ensure_event_loop()
        assert self._loop is not None
        asyncio.run_coroutine_threadsafe(
            self._init_http(url), self._loop,
        ).result()

    async def _init_stdio(self, params):
        self._ctx = stdio_client(params)
        read_stream, write_stream = await self._ctx.__aenter__()
        self.session = ClientSession(read_stream, write_stream)
        await self.session.__aenter__()
        await self.session.initialize()
        tools_res = await self.session.list_tools()
        self.tools_metadata = tools_res.tools

    async def _init_http(self, url):
        self._ctx = sse_client(url)
        read_stream, write_stream = await self._ctx.__aenter__()
        self.session = ClientSession(read_stream, write_stream)
        await self.session.__aenter__()
        await self.session.initialize()
        tools_res = await self.session.list_tools()
        self.tools_metadata = tools_res.tools

    def get_available_tools_names(self) -> List[str]:
        return [tool.name for tool in self.tools_metadata]

    def call_tool_sync(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        if not self.session:
            return "Error: MCP Client is not connected to any server."

        async def _call():
            try:
                assert self.session is not None
                res = await self.session.call_tool(
                    name=tool_name,
                    arguments=arguments,
                )
                if not res.content:
                    return "(no output)"
                return getattr(res.content[0], "text", str(res.content[0]))
            except Exception as e:
                return f"Error executing tool '{tool_name}': {str(e)}"

        assert self._loop is not None
        future = asyncio.run_coroutine_threadsafe(_call(), self._loop)
        return future.result()

    def disconnect(self):
        async def _close():
            try:
                if self.session:
                    await self.session.__aexit__(None, None, None)
            except Exception:
                pass
            try:
                if self._ctx:
                    await self._ctx.__aexit__(None, None, None)
            except Exception:
                pass

        if self._loop is not None:
            if self._loop.is_running():
                asyncio.run_coroutine_threadsafe(_close(), self._loop).result()
                self._loop.call_soon_threadsafe(self._loop.stop)
            if self._thread is not None:
                self._thread.join(timeout=1)
            self._loop = None
            self._thread = None
        self.session = None
        self._ctx = None
        self.tools_metadata = []
