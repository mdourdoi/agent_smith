"""Talks to an MCP server (stdio or HTTP) and exposes plain synchronous
calls the sandbox can use. The async MCP session runs on its own thread so
the rest of the code stays sync.
"""
import asyncio
import os
import shlex
import sys
import threading
from typing import Dict, Any, List
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPClientBridge:
    def __init__(self):
        self.session: ClientSession | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self.tools_metadata: List[Any] = []
        self.resources_metadata: List[Any] = []
        self.prompts_metadata: List[Any] = []
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

    def connect_stdio(self, command, env: dict | None = None):
        """Launch an MCP server over stdio. ``command`` is a command line
        like "python mcp_tools_mbpp.py" (or a list); a bare "python" uses
        the current interpreter. We forward the environment so the server
        sees things like SWEBENCH_TASK_FILE."""
        self._ensure_event_loop()
        assert self._loop is not None
        if isinstance(command, (list, tuple)):
            parts = list(command)
        else:
            parts = shlex.split(command)
        if not parts:
            raise ValueError("Empty MCP stdio command.")
        if parts[0] in ("python", "python3"):
            parts[0] = sys.executable
        server_params = StdioServerParameters(
            command=parts[0],
            args=parts[1:],
            env=env or dict(os.environ),
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
        streams = await self._ctx.__aenter__()
        await self._start_session(streams)

    async def _init_http(self, url):
        if url.rstrip("/").endswith("/sse"):
            from mcp.client.sse import sse_client
            self._ctx = sse_client(url)
        else:
            from mcp.client.streamable_http import streamablehttp_client
            self._ctx = streamablehttp_client(url)
        streams = await self._ctx.__aenter__()
        await self._start_session(streams)

    async def _start_session(self, streams):
        self.session = ClientSession(streams[0], streams[1])
        await self.session.__aenter__()
        await self.session.initialize()
        self.tools_metadata = (await self.session.list_tools()).tools
        self.resources_metadata = await self._safe_list(
            self.session.list_resources, "resources")
        self.prompts_metadata = await self._safe_list(
            self.session.list_prompts, "prompts")

    async def _safe_list(self, list_call, attr: str) -> List[Any]:
        """Fetch resources/prompts, tolerating servers that don't implement
        them (returns an empty list instead of failing the connection)."""
        try:
            return getattr(await list_call(), attr, [])
        except Exception:
            return []

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
