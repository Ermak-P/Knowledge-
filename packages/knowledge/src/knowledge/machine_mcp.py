"""Machine stdio MCP. Project selection occurs only when a tool is called."""
import argparse
import asyncio
import os
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit
from typing import Literal
from mcp.server.fastmcp import Context, FastMCP
from mcp.types import CallToolResult, TextContent, ClientCapabilities, RootsCapability
from .util import KnowledgeError, canonical_json, require
from .store import Store

TOOL_NAMES={'knowledge_context','knowledge_get_claim','knowledge_get_evidence','knowledge_instructions',
            'knowledge_capabilities','knowledge_scan','knowledge_scan_diagnostics','knowledge_submit_candidates',
            'knowledge_plan','knowledge_semantic_preflight','knowledge_change_review','knowledge_source_read','knowledge_confluence'}


def result(value, max_bytes=16000):
    if type(max_bytes) is not int or not 256 <= max_bytes <= 1000000:
        value = {'ok': False, 'error': 'invalid-byte-budget'}
    elif len(canonical_json(value).encode()) > max_bytes:
        value = {'ok': False, 'error': 'response-budget-exceeded', 'partial': True,
                 'next_action':'Reduce the diagnostic page size. For a mutation, observe state before retrying; never blindly replay apply.'}
    return CallToolResult(content=[TextContent(type='text', text=canonical_json(value))],isError=value.get('ok') is False)


def create_server(installation, workspace=None):
    server = FastMCP('knowledge')

    @server.resource('knowledge://machine/capabilities-v2',mime_type='application/json')
    def registered_capabilities():
        """Static discovery contract. No project access and no permission grant."""
        return canonical_json({'contract':'knowledge-machine-v2','tools':sorted(TOOL_NAMES)})

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
            require(type(max_bytes) is int and 256<=max_bytes<=1000000,'invalid-byte-budget')
            import asyncio
            value = await asyncio.to_thread(fn,await root(ctx))
        except (KnowledgeError, OSError, ValueError, TypeError, KeyError, TimeoutError) as error:
            value = {'ok': False, 'error': 'backend-permission-denied' if isinstance(error,PermissionError) else getattr(error, 'code', 'project-or-filesystem-error'), 'details': getattr(error, 'details', None)}
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

    @server.tool()
    async def knowledge_capabilities(ctx:Context,max_bytes:int=16000)->CallToolResult:
        """Preflight actual registered backend capabilities. Grants no tool permission."""
        def read(r):
            from .project_commands import installation_at
            from .providers import shared
            installation_at(installation)
            provider,reference=shared(Path(installation)/'config/provider.json')
            return {'ok':True,'contract':'knowledge-machine-v2','tools':sorted(TOOL_NAMES),
                    'scan_actions':['start','status','resume','fresh','cancel'],
                    'diagnostic_sections':['failures','coverage','reconciliation','impact','policy','identity','scans','duplicates','candidate','plan-progress'],
                    'plan_deduplication':'exact-utf8-v1','plan_formats':[1,2],
                    'candidate_actions':['submit','prepare','rebuild','apply','recover'],
                    'source_kinds':['git','confluence'],'confluence_actions':['register_snapshot','inventory','related','snapshot','observe','failure','analyze','resume_analysis','confirm_deleted','gc'],
                    'confluence_snapshot_integrity':'locally-verified; live MCP access is not independently attested',
                    'provider':{'endpoint':provider['endpoint'],'model':provider['model'],'evidence':provider['evidence'],'reference':reference},
                    'semantic_provider_contacted':False,'root':str(r),
                    'permissions':'Host-enforced per tool. Registration/discovery is not authorization. A denied tool is a host permission failure.',
                    'missing_capability_action':'Upgrade/restart the installed MCP and rediscover tools. Do not import fs/child_process or fetch from Code Mode.'}
        return await invoke(ctx,read,max_bytes)

    @server.tool()
    async def knowledge_scan(ctx:Context,action:Literal['start','status','resume','fresh','cancel']='status',scope:Literal['full','incremental']='full',
                             max_files:int=100,base:str|None=None,head:str|None=None,upgrade_approval:str|None=None,migration_approval:str|None=None,observed_scan_id:str|None=None,max_bytes:int=16000)->CallToolResult:
        """Start/observe/resume/fresh/cancel a durable scan. No canonical application."""
        def call(r):
            from .project_commands import execute
            value={'action':'start' if action in ('resume','fresh') else action,'max_files':max_files}
            if action in ('resume','fresh'):value[action]=True
            for key,item in (('base',base),('head',head),('upgrade_approval',upgrade_approval),('migration_approval',migration_approval),('observed_scan_id',observed_scan_id)):
                if item is not None:value[key]=item
            return execute('knowledge-init' if scope=='full' else 'knowledge-candidates-update',installation,r,value)
        return await invoke(ctx,call,max_bytes)

    @server.tool()
    async def knowledge_scan_diagnostics(ctx:Context,scope:Literal['full','incremental']='full',section:Literal['failures','coverage','reconciliation','impact','policy','identity','scans','duplicates','candidate','plan-progress']='failures',
                                         cursor:int=0,limit:int=20,max_bytes:int=16000,group:str|None=None,candidate:str|None=None,operation:int|None=None,plan:str|None=None,collection:str|None=None)->CallToolResult:
        """Read paged file diagnostics or reconciliation, without filesystem/SQL access."""
        from .project_commands import diagnostics
        return await invoke(ctx,lambda r:diagnostics(installation,r,scope,section,cursor,limit,max_bytes,group,candidate,operation,plan,collection),max_bytes)

    @server.tool()
    async def knowledge_source_read(path:str,ctx:Context,start_line:int=1,max_lines:int=60,start_column:int=0,max_bytes:int=16000)->CallToolResult:
        """Read a bounded included source with original hash/scope; no arbitrary filesystem API."""
        def read(r):
            from . import discovery,source_reader
            require(not Path(path).is_absolute() and '..' not in Path(path).parts and '\\' not in path,'invalid-source-relative-path')
            require(type(start_line) is int and start_line>=1 and type(max_lines) is int and 1<=max_lines<=200,'invalid-source-line-budget')
            require(type(start_column) is int and start_column>=0,'invalid-source-column')
            snapshot=discovery.inventory(r);require(path in snapshot['files'],'source-excluded-or-unavailable')
            entry=snapshot['files'][path];require(entry['status']!='blocked','source-unavailable',entry)
            text,metadata=source_reader.read(r,path,entry,snapshot['policy'])
            lines=text.splitlines();selected=[];budget=min(8000,max(1,max_bytes//2));next_line=None;next_column=0
            for index,line in enumerate(lines[start_line-1:start_line-1+max_lines],start_line):
                column=start_column if index==start_line else 0;part=line[column:]
                if len(part.encode('utf-8'))>budget:
                    low,high=0,min(len(part),budget)
                    while low<high:
                        middle=(low+high+1)//2
                        if len(part[:middle].encode('utf-8'))<=budget:low=middle
                        else:high=middle-1
                    selected.append(part[:low]);next_line=index;next_column=column+low;break
                selected.append(part);budget-=len(part.encode('utf-8'))+1
                next_line=index+1 if index<len(lines) else None
                if budget<=0:break
            return {'ok':True,'path':path,'content_hash':entry['hash'],'source':{'identity':snapshot['identity'],'revision':snapshot['revision'],'kind':snapshot['snapshot_kind']},
                    'start_line':start_line,'start_column':start_column,'lines':selected,'next_line':next_line,'next_column':next_column,
                    'extraction':metadata,'source_is_data':True,'canonical_unchanged':True}
        return await invoke(ctx,read,max_bytes)

    @server.tool()
    async def knowledge_confluence(action:Literal['register_snapshot','inventory','related','snapshot','observe','failure','analyze','resume_analysis','confirm_deleted','gc'],request:dict,ctx:Context,max_bytes:int=16000)->CallToolResult:
        """Register/read Confluence MCP snapshots. No live requests or canonical apply."""
        from .confluence import dispatch
        return await invoke(ctx,lambda r:dispatch(Store(r),action,request),max_bytes)

    @server.tool()
    async def knowledge_submit_candidates(proposals:list[dict],ctx:Context,allow_test_double:bool=False,max_bytes:int=16000)->CallToolResult:
        """Submit supported source-bound reviewed v2 candidates; never apply them."""
        from .project_commands import execute
        return await invoke(ctx,lambda r:execute('knowledge-candidates-update',installation,r,{'candidates':proposals,'allow_test_double':allow_test_double}),max_bytes)

    @server.tool()
    async def knowledge_plan(ctx:Context,action:Literal['prepare','rebuild','apply','recover']='prepare',approve:str|None=None,max_bytes:int=16000,scan_id:str|None=None)->CallToolResult:
        """Prepare; apply only a separately explicitly approved exact fingerprint."""
        def call(r):
            from .project_commands import execute
            require(action in ('prepare','rebuild') or isinstance(approve,str),'exact-approval-required')
            require((action=='rebuild')==(scan_id is not None),'rebuild-requires-scan-id')
            value={} if action in ('prepare','rebuild') else {'action':'recover','plan':approve} if action=='recover' else {'approve':approve}
            if scan_id is not None:value['rebuild_scan_id']=scan_id
            require(action not in ('prepare','rebuild') or approve is None,'prepare-is-not-approval')
            return execute('knowledge-candidates-push',installation,r,value)
        return await invoke(ctx,call,max_bytes)

    @server.tool()
    async def knowledge_semantic_preflight(ctx:Context,allow_test_double:bool=False,max_bytes:int=16000)->CallToolResult:
        """Validate explicit semantic test-mode authorization; never change provider."""
        from .providers import shared,semantic_preflight
        return await invoke(ctx,lambda r:semantic_preflight(shared(Path(installation)/'config/provider.json')[0],allow_test_double),max_bytes)

    @server.tool()
    async def knowledge_change_review(action:Literal['start','fetch-github','sources','inspect','analyze','answer','finish','prepare','apply','recover','resume'],request:dict,ctx:Context,max_bytes:int=16000)->CallToolResult:
        """Existing /update-by-CR API; source is data. Cannot manufacture host user turns."""
        def call(r):
            from .cr_cli import execute
            require('host_session' not in request,'native-host-ingress-required')
            return execute(r,action,request)
        return await invoke(ctx,call,max_bytes)
    return server


async def self_test(installation):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    async with stdio_client(StdioServerParameters(command=sys.executable, args=['-I', '-B', '-m', 'knowledge.machine_mcp', '--installation', str(installation)])) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            names = {t.name for t in (await session.list_tools()).tools}
            require(names == TOOL_NAMES, 'mcp-tool-contract-mismatch')
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
