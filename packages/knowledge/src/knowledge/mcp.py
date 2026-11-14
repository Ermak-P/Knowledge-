"""Optional read-only stdio MCP adapter using the same Store and resolver."""
import argparse
from .store import Store
from .util import KnowledgeError


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
    def knowledge_context(task:str,max_bytes:int=16000,max_items:int=10,include_unconfirmed:bool=False)->dict:
        """Retrieve bounded context, preserving confidence, provenance and conflicts."""
        return call(store.context,task,max_bytes,max_items,include_unconfirmed)

    @server.tool()
    def knowledge_get_claim(identifier:str)->dict:
        """Read a claim by stable ID."""
        return call(store.lookup,'claims',identifier)

    @server.tool()
    def knowledge_get_evidence(identifier:str)->dict:
        """Read evidence by stable ID."""
        return call(store.lookup,'evidence',identifier)
    return server


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',required=True)
    args=p.parse_args()
    create_server(args.root).run(transport='stdio')


if __name__=='__main__':
    main()
