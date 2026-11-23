"""Machine stdio MCP. Project selection occurs only when a tool is called."""
import argparse
import asyncio
import os
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit
from mcp.server.fastmcp import Context, FastMCP
from mcp.types import CallToolResult, TextContent, ClientCapabilities, RootsCapability
from .util import KnowledgeError, canonical_json, require
from .store import Store


def result(value, max_bytes=16000):
    if type(max_bytes) is not int or not 256 <= max_bytes <= 1000000:
        value = {'ok': False, 'error': 'invalid-byte-budget'}
    elif len(canonical_json(value).encode()) > max_bytes:
        value = {'ok': False, 'error': 'response-budget-exceeded', 'partial': True}
    return CallToolResult(content=[TextContent(type='text', text=canonical_json(value))])


def create_server(installation, workspace=None):
    server = FastMCP('knowledge')

    async def root(ctx):
        directory = workspace or os.getcwd()
        session = ctx.request_context.session
        if session.check_client_capability(ClientCapabilities(roots=RootsCapability())):
            roots = (await asyncio.wait_for(session.list_roots(), timeout=10)).roots
            require(len(roots) == 1, 'ambiguous-or-missing-workspace-roots')
            uri = urlsplit(str(roots[0].uri))
            require(uri.scheme == 'file' and uri.netloc in ('', 'localhost'), 'unsupported-workspace-uri')
            directory = unquote(uri.path)
            if os.name == 'nt' and directory.startswith('/') and len(directory) > 2 and directory[2] == ':':
                directory = directory[1:]
        from .project_commands import resolve_root
        selected = resolve_root(directory)
        require(not selected.is_relative_to(Path(installation).absolute()), 'installation-is-not-a-project')
        return selected

    async def invoke(ctx, fn, max_bytes):
        try:
            value = fn(await root(ctx))
        except (KnowledgeError, OSError, ValueError, TypeError, TimeoutError) as error:
            value = {'ok': False, 'error': getattr(error, 'code', 'project-or-filesystem-error'), 'details': getattr(error, 'details', None)}
        return result(value, max_bytes)

    @server.tool()
    async def knowledge_context(task: str, ctx: Context, max_bytes: int = 16000, max_items: int = 10, include_unconfirmed: bool = False) -> CallToolResult:
        """Read bounded project context; no initialization or project mutation."""
        return await invoke(ctx, lambda r: Store(r).context(task, max_bytes, max_items, include_unconfirmed), max_bytes)

    @server.tool()
    async def knowledge_get_claim(identifier: str, ctx: Context, history: bool = False, max_bytes: int = 16000) -> CallToolResult:
        """Read a stable claim or its lifecycle history."""
        from .lifecycle import history as read_history
        return await invoke(ctx, lambda r: read_history(Store(r), identifier) if history else Store(r).lookup('claims', identifier), max_bytes)

    @server.tool()
    async def knowledge_get_evidence(identifier: str, ctx: Context, max_bytes: int = 16000) -> CallToolResult:
        """Read evidence without changing canonical knowledge."""
        return await invoke(ctx, lambda r: Store(r).lookup('evidence', identifier), max_bytes)

    @server.tool()
    async def knowledge_instructions(tool: str, name: str, ctx: Context, max_bytes: int = 12000, environment: dict | None = None) -> CallToolResult:
        """Read applicable instructions; never creates execution authority."""
        from .operations import lookup
        import platform
        return await invoke(ctx, lambda r: lookup(r, {'tool': tool, 'name': name}, {'machine': platform.node(), 'os': sys.platform, **(environment or {})}, shared=Path(installation) / 'shared', max_bytes=max_bytes), max_bytes)
    return server


async def self_test(installation):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    async with stdio_client(StdioServerParameters(command=sys.executable, args=['-I', '-B', '-m', 'knowledge.machine_mcp', '--installation', str(installation)])) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            names = {t.name for t in (await session.list_tools()).tools}
            require(names == {'knowledge_context', 'knowledge_get_claim', 'knowledge_get_evidence', 'knowledge_instructions'}, 'mcp-tool-contract-mismatch')
    print(canonical_json({'ok': True, 'transport': 'stdio', 'tools': sorted(names), 'project_access': False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installation', required=True)
    parser.add_argument('--workspace')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        asyncio.run(self_test(args.installation))
    else:
        create_server(args.installation, args.workspace).run(transport='stdio')


if __name__ == '__main__':
    main()
