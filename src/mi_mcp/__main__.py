"""Entry point for the MI MCP Server.

Transport: **stdio only** in this version (Claude Desktop / Claude Code / Cursor).
The networked transports (sse / streamable-http) are disabled — they shipped
without inbound auth, TLS, or CORS, so selecting one exits with an error. They
will return in a later release with OAuth 2.1 + TLS.

Usage:
  mi-mcp            # run the server over stdio
  mi-mcp setup      # one command: store key → wire → opt-in → verify (alias: init)
  mi-mcp wire       # wire into Claude Desktop / Code / Cursor (no key in configs)
  mi-mcp doctor     # verify install + key resolution + wiring
  mi-mcp status     # show wired surfaces + opt-in allowlist
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from . import __version__

logger = logging.getLogger("mi_mcp")


def main():
    # Admin subcommands: `mi-mcp {setup|init|wire|doctor|status|memory}`. Bare
    # `mi-mcp` (no subcommand) runs the server — that's how the MCP host spawns it.
    argv = sys.argv[1:]
    if argv and argv[0] in ("setup", "init", "wire", "doctor", "status", "memory"):
        from .cli import run_admin
        sys.exit(run_admin(argv[0], argv[1:]))

    parser = argparse.ArgumentParser(
        prog="mi-mcp",
        description="MemoryIntelligence MCP Server",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"mi-mcp {__version__}",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default=None,
        help="Transport (stdio only in this version; sse/streamable-http are "
             "disabled and exit with an error). Default: stdio.",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Bind host for SSE/HTTP (default: 127.0.0.1 loopback, or MI_HOST env var)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Bind port for SSE/HTTP (default: 8100, or MI_PORT env var)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Log level (default: INFO)",
    )
    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    # Load config from env (CLI args override env vars)
    from .config import MIConfig

    try:
        config = MIConfig.from_env()
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)

    # CLI args override config/env
    if args.transport:
        config = MIConfig(
            api_key=config.api_key,
            base_url=config.base_url,
            default_scope=config.default_scope,
            default_retention=config.default_retention,
            default_pii_handling=config.default_pii_handling,
            transport=args.transport,
            host=args.host or config.host,
            port=args.port or config.port,
        )
    elif args.host or args.port:
        config = MIConfig(
            api_key=config.api_key,
            base_url=config.base_url,
            default_scope=config.default_scope,
            default_retention=config.default_retention,
            default_pii_handling=config.default_pii_handling,
            transport=config.transport,
            host=args.host or config.host,
            port=args.port if args.port else config.port,
        )

    # Create server
    from .server import create_server

    server = create_server(config)

    transport = config.transport
    logger.info(f"Starting MI MCP Server (transport={transport})")

    # v0 is stdio-only. The networked transports (sse/streamable-http) shipped with no
    # inbound auth, TLS, or CORS, so they are disabled here to remove that attack surface
    # entirely (DNS rebinding, browser CSRF, unauthenticated access). They return in a
    # later version with OAuth 2.1 + TLS.
    if transport != "stdio":
        logger.error(
            "Transport '%s' is not supported in this version — stdio only. "
            "Networked transports (with auth + TLS) are planned for a future release.",
            transport,
        )
        sys.exit(2)

    from mcp.server.stdio import stdio_server

    async def run_stdio():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    asyncio.run(run_stdio())


if __name__ == "__main__":
    main()
