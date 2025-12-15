import os
from contextlib import asynccontextmanager
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult
from yinqing.utils.logger import get_logger

logger = get_logger(__name__)

@asynccontextmanager
async def init_session(host, port, transport):
    if transport == 'sse':
        url = f'http://{host}:{port}/sse'
        async with sse_client(url) as (read_stream, write_stream):
            async with ClientSession(
                read_stream=read_stream, write_stream=write_stream
            ) as session:
                await session.initialize()
                yield session
    elif transport == 'stdio':
        # Assuming we want to run the server in the same env
        env = os.environ.copy()
        stdio_params = StdioServerParameters(
            command='uv',
            args=['run', 'a2a-mcp'], # This might need adjustment based on how user runs the server
            env=env,
        )
        async with stdio_client(stdio_params) as (read_stream, write_stream):
            async with ClientSession(
                read_stream=read_stream,
                write_stream=write_stream,
            ) as session:
                await session.initialize()
                yield session
    else:
        raise ValueError(f"Unsupported transport type: {transport}")

async def find_agent(session: ClientSession, query: str) -> CallToolResult:
    logger.info(f"Calling 'find_agent' tool with query: '{query[:50]}...'")
    return await session.call_tool(
        name='find_agent',
        arguments={
            'query': query,
        },
    )

async def list_all_agents(session: ClientSession) -> CallToolResult:
    logger.info(f"Calling 'list_all_agents' tool")
    return await session.call_tool(
        name='list_all_agents',
        arguments={},
    )
