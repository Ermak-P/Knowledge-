"""Optional read-only stdio MCP adapter using the same Store and resolver."""
import argparse
from .store import Store
from .util import KnowledgeError, canonical_json
from mcp.types import CallToolResult, TextContent


def create_server(root,shared_root=None):
    from mcp.server.fastmcp import FastMCP
    server=FastMCP('knowledge')
    store=Store(root)

    def call(fn, *args, **kwargs):
        try:
            return fn(*args,**kwargs)
        except (KnowledgeError,OSError,ValueError,TypeError) as e:
            return {'ok':False,'error':getattr(e,'code','memory-or-filesystem-error'),'details':getattr(e,'details',None)}

    @server.tool()
    def knowledge_instructions(tool:str,name:str,max_bytes:int=12000,environment:dict|None=None)->CallToolResult:
        """Read applicable operational instructions; never creates user authority."""
        from .operations import lookup
        import platform
        value=call(lookup,root,{'tool':tool,'name':name},{'machine':platform.node(),'os':__import__('sys').platform,**(environment or {})},shared=shared_root,max_bytes=max_bytes)
        return CallToolResult(content=[TextContent(type='text',text=canonical_json(value))])

    @server.tool()
    def knowledge_context(task:str,max_bytes:int=16000,max_items:int=10,include_unconfirmed:bool=False)->CallToolResult:
        """Retrieve bounded context, preserving confidence, provenance and conflicts."""
        value=call(store.context,task,max_bytes,max_items,include_unconfirmed)
        # Text only: no duplicate structuredContent payload. JSON-RPC envelope is
        # outside the application budget; this exact UTF-8 text is inside it.
        return bounded(value,max_bytes)

    def bounded(value,max_bytes):
        if type(max_bytes) is not int or not 256<=max_bytes<=1000000:
            value={'ok':False,'error':'invalid-byte-budget'}
        elif len(canonical_json(value).encode())>max_bytes:
            value={'ok':False,'error':value.get('error','retrieval-error'),'details_truncated':True} if value.get('ok') is False else {'ok':True,'result':'budget-too-small','records':[],'partial':True}
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
    p.add_argument('--shared-root')
    args=p.parse_args()
    create_server(args.root,args.shared_root).run(transport='stdio')


if __name__=='__main__':
    main()
