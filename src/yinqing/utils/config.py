import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class MCPServerConfig:
    host: str = "localhost"
    port: int = 8000
    transport: str = "sse" # or stdio, http

def init_api_key():
    """Ensure OpenAI API Key is set for Qwen3-max."""
    if not os.getenv("OPENAI_API_KEY"):
        # You might want to log a warning or error here
        pass

def get_mcp_server_config() -> MCPServerConfig:
    """Get MCP Server configuration from env or defaults."""
    host = os.getenv("MCP_SERVER_HOST", "localhost")
    port = int(os.getenv("MCP_SERVER_PORT", "8000"))
    transport = os.getenv("MCP_SERVER_TRANSPORT", "sse")
    return MCPServerConfig(host=host, port=port, transport=transport)
