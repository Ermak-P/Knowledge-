"""Optional read-only stdio MCP adapter using the same Store and resolver."""
import argparse
from .store import Store
from .util import KnowledgeError, canonical_json
from mcp.types import CallToolResult, TextContent


def create_server(root):
    from mcp.server.fastmcp import FastMCP
    server=FastMCP('knowledge')
    store=Store(root)

    def call(fn, *args, **kwargs):
        try:
            return fn(*args,**kwargs)
        except KnowledgeError as e:
            return {'ok':False,'error':e.code,'details':e.details}

    @server.tool()
    def knowledge_context(task:str,max_bytes:int=16000,max_items:int=10,include_unconfirmed:bool=False)->CallToolResult:
        """Retrieve bounded context, preserving confidence, provenance and conflicts."""
        value=call(store.context,task,max_bytes,max_items,include_unconfirmed)
        # Text only: no duplicate structuredContent payload. JSON-RPC envelope is
        # outside the application budget; this exact UTF-8 text is inside it.
        return CallToolResult(content=[TextContent(type='text',text=canonical_json(value))])

    def bounded(value,max_bytes):
        if type(max_bytes) is not int or not 256<=max_bytes<=1000000:
            value={'ok':False,'error':'invalid-byte-budget'}
        elif len(canonical_json(value).encode())>max_bytes:
            value={'ok':True,'result':'budget-too-small','records':[]}
        return CallToolResult(content=[TextContent(type='text',text=canonical_json(value))])

    @server.tool()
    def knowledge_get_claim(identifier:str,history:bool=False,max_bytes:int=16000)->CallToolResult:
        """Read a claim by stable ID."""
        if history:
            from .lifecycle import history as read_history
            return bounded(call(read_history,store,identifier),max_bytes)
        return bounded(call(store.lookup,'claims',identifier),max_bytes)

    @server.tool()
    def knowledge_get_evidence(identifier:str,max_bytes:int=16000)->CallToolResult:
        """Read evidence by stable ID."""
        return bounded(call(store.lookup,'evidence',identifier),max_bytes)
    return server


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',required=True)
    args=p.parse_args()
    create_server(args.root).run(transport='stdio')


if __name__=='__main__':
    main()
