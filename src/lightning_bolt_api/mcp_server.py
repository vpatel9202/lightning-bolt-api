"""MCP server entry point.

The server will expose the same read-only capabilities as the Python client and
CLI. It should support stdio for host-local MCP clients and streamable HTTP for
host service mode and Docker.
"""

from __future__ import annotations


def main() -> None:
    raise NotImplementedError("MCP server implementation is planned in AGENTS.md.")
