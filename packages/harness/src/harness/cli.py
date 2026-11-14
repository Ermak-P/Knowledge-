import argparse
import sys
from knowledge.util import canonical_json, KnowledgeError
from .consumer import context


def main():
    p=argparse.ArgumentParser(description='Read-only Harness Knowledge consumer')
    p.add_argument('--root',required=True)
    p.add_argument('--task',required=True)
    p.add_argument('--max-bytes',type=int)
    p.add_argument('--include-unconfirmed',action='store_true')
    a=p.parse_args()
    try:
        result=context(a.root,a.task,a.max_bytes,a.include_unconfirmed)
    except (KnowledgeError,OSError) as e:
        result={'ok':False,'error':getattr(e,'code','filesystem-error')}
    print(canonical_json(result))
    return 0 if result['ok'] else 1


if __name__=='__main__':
    sys.exit(main())
