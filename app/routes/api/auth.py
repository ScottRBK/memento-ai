"""Authentication info endpoint for frontend configuration detection."""

from starlette.requests import Request
from starlette.responses import JSONResponse
from fastmcp import FastMCP
from fastmcp.server.auth.auth import OAuthProvider
import logging

logger = logging.getLogger(__name__)

# Provider class name to OAuth provider identifier mapping
OAUTH_PROVIDER_MAP = {
    "GitHubProvider": "github",
    "GoogleProvider": "google",
    "AzureProvider": "azure",
    "Auth0Provider": "auth0",
    "DiscordProvider": "discord",
    "SupabaseProvider": "supabase",
    "WorkOSProvider": "workos",
    "DescopeProvider": "descope",
    "ScalekitProvider": "scalekit",
    "OCIProvider": "oci",
    "AWSProvider": "aws",
    "AWSCognitoProvider": "aws",
}


def register(mcp: FastMCP):
    """Register auth info routes with FastMCP"""

    @mcp.custom_route("/api/v1/auth/info", methods=["GET"])
    async def get_auth_info(request: Request) -> JSONResponse:
        """
        Get authentication configuration info (public endpoint).

        No authentication required - used by frontend to detect auth mode
        before user is authenticated.

        Returns:
            JSONResponse with auth configuration:
            - authEnabled: bool - whether auth is configured
            - authMode: str - "disabled", "oauth", "jwt", or "introspection"
            - oauthProviders: list[str] - OAuth provider identifiers (e.g., ["github"])
            - loginUrl: str | None - OAuth authorization endpoint if applicable
        """
        # Check if auth is enabled
        if mcp.auth is None:
            return JSONResponse({
                "authEnabled": False,
                "authMode": "disabled",
                "oauthProviders": [],
                "loginUrl": None
            })

        # Auth is enabled - determine mode
        provider_name = type(mcp.auth).__name__
        logger.debug(f"Auth provider class: {provider_name}")

        # Check if OAuth provider (inherits from OAuthProvider)
        if isinstance(mcp.auth, OAuthProvider):
            oauth_id = OAUTH_PROVIDER_MAP.get(provider_name, "unknown")
            return JSONResponse({
                "authEnabled": True,
                "authMode": "oauth",
                "oauthProviders": [oauth_id],
                "loginUrl": "/authorize"
            })

        # Check for introspection provider
        if "Introspection" in provider_name:
            return JSONResponse({
                "authEnabled": True,
                "authMode": "introspection",
                "oauthProviders": [],
                "loginUrl": None
            })

        # Default to JWT for TokenVerifier subclasses
        return JSONResponse({
            "authEnabled": True,
            "authMode": "jwt",
            "oauthProviders": [],
            "loginUrl": None
        })
