"""Independent expected changes; scripted decisions only, never direct source writes."""
from knowledge.util import loads
from p2_fixtures import FixtureProvider,calls,final

BASKET='src/ApplicationCore/Entities/BasketAggregate/BasketItem.cs'
NEW_TEST='tests/UnitTests/ApplicationCore/Entities/BasketItemOverflow.cs'
OVERFLOW_TEST='''using System;
using Microsoft.eShopWeb.ApplicationCore.Entities.BasketAggregate;
using Xunit;
namespace UnitTests.ApplicationCore.Entities;
public class BasketItemOverflow
{
    [Fact]
    public void AddQuantityRejectsOverflowAndPreservesQuantity()
    {
        var item = new BasketItem(1, int.MaxValue, 1m);
        Assert.Throws<OverflowException>(() => item.AddQuantity(1));
        Assert.Equal(int.MaxValue, item.Quantity);
    }
}
'''

class EditScenario(FixtureProvider):
    def __init__(self,path,desired,additions=None,repair=False,first_source=None,deny=False):
        super().__init__(path,desired,repair=repair,deny=deny)
        self.edits={path:desired,**(additions or {})};self.first_source=first_source
    def decide(self,body):
        system=loads(body['messages'][0]['content']);role=system['runtime_role'];agent=system['agent'];turn=self.agent_turns[agent]
        if role!='Coding' or self.deny:return super().decide(body)
        self.requests.append(body);self.agent_turns[agent]+=1
        if agent not in self.coding_agents:self.coding_agents.append(agent)
        if turn==0:return calls(*[('read',{'path':p}) for p in self.edits])
        if turn==1:
            receipts=[loads(m['content']) for m in body['messages'] if m['role']=='tool']
            hashes={r['path']:r['sha256'] for r in receipts if r.get('sha256')}
            edits=dict(self.edits)
            if self.repair and self.coding_agents.index(agent)==0:edits[self.path]=self.first_source
            return calls(('patch',{'files':[{'path':p,'before':hashes.get(p),'after':text} for p,text in edits.items()]}))
        return final('All declared edits submitted through Coding patch.')
