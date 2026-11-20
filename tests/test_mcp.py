from datetime import timedelta
import asyncio
from pathlib import Path
import sys
import tempfile
import unittest
from mcp import ClientSession, StdioServerParameters, stdio_client
from knowledge.store import Store
from knowledge.util import loads
from harness.consumer import context
from fixtures import addition,legacy_fixture
from knowledge import migration


class McpTests(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_cli_agreement_two_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            roots=[Path(tmp)/'project один',Path(tmp)/'project один2']
            for i,root in enumerate(roots):
                root.mkdir();s=Store(root);s.init();s.submit(addition(f'synthetic.root{i}',f'Synthetic unique root{i} rule.'))
                p=s.prepare()['fingerprint'];s.apply(p,p);s.acknowledge(p)
            for i,root in enumerate(roots):
                params=StdioServerParameters(command=sys.executable,args=['-B','-m','knowledge.mcp','--root',str(root)])
                async with stdio_client(params) as (reader,writer):
                    async with ClientSession(reader,writer,read_timeout_seconds=timedelta(seconds=120)) as session:
                        await session.initialize()
                        tools=await session.list_tools()
                        self.assertEqual({t.name for t in tools.tools},{'knowledge_context','knowledge_get_claim','knowledge_get_evidence','knowledge_instructions'})
                        for tool,kind,identifier in [('knowledge_get_claim','claims',f'synthetic.root{i}'),('knowledge_get_evidence','evidence',f'evidence.synthetic.root{i}')]:
                            r=await session.call_tool(tool,{'identifier':identifier})
                            self.assertFalse(r.isError);self.assertEqual(loads(r.content[0].text),Store(root).lookup(kind,identifier))
                        r=await session.call_tool('knowledge_context',{'task':f'synthetic.root{i}'})
                        expected=Store(root).context(f'synthetic.root{i}')
                        self.assertEqual(loads(r.content[0].text),expected)
                        self.assertEqual(context(root,f'synthetic.root{i}')['context']['claims'],expected['claims'])
                        proc=await asyncio.create_subprocess_exec(sys.executable,'-m','knowledge.cli','context','--root',str(root),'--task',f'synthetic.root{i}',stdout=asyncio.subprocess.PIPE)
                        out,_=await proc.communicate();self.assertEqual(proc.returncode,0);self.assertEqual(loads(out),expected)
                        r=await session.call_tool('knowledge_get_claim',{'identifier':f'synthetic.root{1-i}'})
                        self.assertEqual(loads(r.content[0].text)['result'],'no-match')

    async def test_conflicts_and_unconfirmed_stdio(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);legacy_fixture(root);p=migration.preview(root);migration.apply(root,p['fingerprint'])
            params=StdioServerParameters(command=sys.executable,args=['-B','-m','knowledge.mcp','--root',str(root)])
            async with stdio_client(params) as (reader,writer):
                async with ClientSession(reader,writer,read_timeout_seconds=timedelta(seconds=120)) as session:
                    await session.initialize()
                    r=await session.call_tool('knowledge_context',{'task':'synthetic.confirmed synthetic.inferred','include_unconfirmed':True})
                    value=loads(r.content[0].text)
                    self.assertEqual(value,Store(root).context('synthetic.confirmed synthetic.inferred',include_unconfirmed=True))
                    self.assertEqual({c['status'] for c in value['claims']},{'CONFIRMED','INFERRED'})
                    self.assertTrue(value['conflicts']);self.assertTrue(all(c['provenance'] for c in value['claims']))
