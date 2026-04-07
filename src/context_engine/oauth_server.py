"""OAuth Server pre Context Engine.

Samostatný OAuth 2.1 server, ktorý autentifikuje prístup
ku Context Engine MCP serveru. Beží na porte 9000.
"""

import os
import sys
from mcp_oauth import OAuthServer, AuthServerSettings, SimpleAuthSettings


def main():
    port = int(os.environ.get("CTX_OAUTH_PORT", "9000"))
    host = os.environ.get("CTX_OAUTH_HOST", "0.0.0.0")
    username = os.environ.get("CTX_OAUTH_USER", "satori")
    password = os.environ.get("CTX_OAUTH_PASS")

    if not password:
        print("ERROR: CTX_OAUTH_PASS environment variable is required", file=sys.stderr)
        sys.exit(1)

    # server_url must be localhost (not 0.0.0.0) for OAuth issuer validation
    server_url = f"http://localhost:{port}"

    server_settings = AuthServerSettings(
        host=host,
        port=port,
        server_url=server_url,
        auth_callback_path=f"{server_url}/login",
    )
    auth_settings = SimpleAuthSettings(
        superusername=username,
        superuserpassword=password,
        mcp_scope="user",
    )

    oauth_server = OAuthServer(
        server_settings=server_settings,
        auth_settings=auth_settings,
    )

    print(f"OAuth server starting on {host}:{port} (user: {username})")
    oauth_server.run_starlette_server()


if __name__ == "__main__":
    main()
