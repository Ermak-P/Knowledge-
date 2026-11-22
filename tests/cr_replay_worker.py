"""Controlled fresh planner: task + normal context only, no interview/oracle.

Generic extraction of explicit fixture parameters and preserved constraints is a
protocol/behavior test, NOT evidence about an arbitrary language model.
"""
import json,re,sys
from pathlib import Path
from knowledge.store import Store
import knowledge


def main():
    assert Path(knowledge.__file__).is_relative_to(Path(sys.prefix))
    root,task=sys.argv[1:3]
    context=Store(root).context(task,max_bytes=16000,max_items=10)
    parameters={};preserve=[];reasons=[]
    for claim in context['claims']:
        statement=claim['statement']
        for key,value in re.findall(r'\b([a-z_]{2,50})\s*=\s*([0-9]+)\b',statement):
            number=int(value)
            if key in parameters and parameters[key]!=number:raise ValueError('conflicting retrieved parameter')
            parameters[key]=number
        preserve.extend(re.findall(r'Preserve / Сохранить: ([^.]+)',statement))
        reasons.extend(re.findall(r'Reason / Причина: ([^.]+)',statement))
    print(json.dumps(dict(profile='controlled-fresh-planner',input_task=task,retrieved=context,plan=dict(parameters=parameters,preserve=preserve,reasons=reasons)),ensure_ascii=False))
if __name__=='__main__':main()
