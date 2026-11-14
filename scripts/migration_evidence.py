"""Generate reproducible, explicitly synthetic migration artifacts."""
import json
from pathlib import Path
import sys
import tempfile
from knowledge import migration
from knowledge.store import Store

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from fixtures import legacy_fixture


def main():
    with tempfile.TemporaryDirectory(prefix='knowledge-migration-evidence-') as tmp:
        root=Path(tmp)/'synthetic legacy';root.mkdir()
        records,queue=legacy_fixture(root)
        before=migration.snapshot(root);plan=migration.preview(root)
        result=migration.apply(root,plan['fingerprint']);after=Store(root).export()
        for g,values in records.items():
            assert sorted(after['records'][g],key=lambda x:x['id'])==sorted(values,key=lambda x:x['id'])
        assert after['history'][0]['legacy_queue']==queue
        assert {q['id']:q['status'] for q in after['queue']}=={q['id']:q['status'] for q in queue}
        assert migration.snapshot(root)==before
        repeat=migration.apply(root,plan['fingerprint'])
        restore=root.parent/'restored';migration.restore_legacy(root,restore)
        original=root/'.ai'
        assert {p.relative_to(original).as_posix():p.read_bytes() for p in original.rglob('*') if p.is_file()}=={p.relative_to(restore).as_posix():p.read_bytes() for p in restore.rglob('*') if p.is_file()}
        report={'synthetic':True,'status':'PASS','semantic_diff':plan['manifest']['semantic_diff'],
                'before':{'records':records,'queue':queue},'after':after,'manifest':plan['manifest'],
                'source_unchanged':True,'restoration_byte_equal':True,'repeat':repeat,
                'note':'Journal/plan fixtures use supplied sealed-document shape. They are invented fixtures, not historical approvals.'}
        (ROOT/'reports/P0/migration-results.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
        print('PASS: synthetic values, identities, relations, queue states/history, source immutability and restore')


if __name__=='__main__':main()
