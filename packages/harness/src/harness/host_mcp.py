"""Optional companion MCP: reads plus only explicitly enrolled guarded tasks."""
import argparse
from knowledge.util import KnowledgeError,canonical_json

def create_server(root):
    from mcp.server.fastmcp import FastMCP
    from mcp.types import CallToolResult,TextContent
    from .companion import doctor,run_task
    from .engine import status
    server=FastMCP('harness-companion')
    def call(fn,*args):
        try:value=fn(*args)
        except (KnowledgeError,OSError,ValueError) as e:value={'ok':False,'error':getattr(e,'code','companion-error')}
        text=canonical_json(value)
        if len(text.encode())>20000:text=canonical_json({'ok':True,'result':'artifact-too-large-use-local-status-cli'})
        return CallToolResult(content=[TextContent(type='text',text=text)])
    @server.tool()
    def harness_discover_tests()->CallToolResult:
        from .testing import inspect
        return call(inspect,root)
    @server.tool()
    def harness_doctor()->CallToolResult:return call(doctor,root)
    @server.tool()
    def harness_status(run_id:str)->CallToolResult:return call(status,root,run_id)
    @server.tool()
    def harness_run(task_name:str)->CallToolResult:return call(run_task,root,task_name)
    return server

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);a=p.parse_args();create_server(a.root).run(transport='stdio')
if __name__=='__main__':main()
