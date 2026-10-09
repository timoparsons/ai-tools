"""FastMCP stdio server. Register in Bifrost as a stdio client."""
from mcp.server.fastmcp import FastMCP

import tools

mcp = FastMCP("bifrost-admin")
for fn in (
    tools.bifrost_status,
    tools.bifrost_list_mcp_clients,
    tools.bifrost_get_mcp_client,
    tools.bifrost_get_config,
    tools.bifrost_list_plugins,
    tools.bifrost_reconnect_mcp_client,
    tools.bifrost_create_mcp_client,
    tools.bifrost_update_mcp_client,
    tools.bifrost_delete_mcp_client,
):
    mcp.tool()(fn)

if __name__ == "__main__":
    mcp.run()
