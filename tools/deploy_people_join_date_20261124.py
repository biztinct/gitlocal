"""Guarded Python-only deployment; shared schema, assets and manifests unchanged.

Run as root on Payobook19v2 with a private staging directory. Requires the
reviewed inventory, patched pb_people file and revision.txt in that directory.
"""
import ast
import datetime
import fcntl
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

stage = Path(sys.argv[1]).resolve()
assert str(stage).startswith('/tmp/sudima-bank-release-')
live = Path('/odoo/odoo-server/addons')
inventory = json.loads((stage / 'inventory.json').read_text())
revision = (stage / 'revision.txt').read_text().strip()
dbs = ['payobook', 'payobook_template', 'p0clone', 'rize', 'sudima']
lock = open('/tmp/payobook-studio-deploy.lock', 'a+')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)


def files(folder):
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob('*') if p.is_file() and not p.is_symlink()
            and p.name != '.DS_Store' and '__pycache__' not in p.parts and p.suffix not in ('.pyc', '.pyo')}


def sql(db, query):
    return subprocess.check_output(['sudo', '-u', 'postgres', 'psql', '-X', '-At', '-d', db, '-c', query], text=True).strip()


def note(state, detail):
    with Path('/opt/deploy-notes.md').open('a') as f:
        f.write(f'{datetime.datetime.now(datetime.timezone.utc).isoformat()} | Codex Sudima joining date | {state} | pb_people | '
                + ','.join(dbs) + f' | Python-only restart | {revision}; {detail}\n')


for name, data in inventory['modules'].items():
    assert files(live / name) == data['files'], ('Concurrent module change', name)
for db in dbs:
    actual = dict(x.split('|', 1) for x in sql(db, "SELECT name,latest_version FROM ir_module_module WHERE state='installed'").splitlines())
    for name, data in inventory['modules'].items():
        if name in actual:
            assert actual[name] == data['version'], (db, name, 'version mismatch')
    assert 'pb_people' in actual
    assert not sql(db, "SELECT name FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove')")
old = live / 'pb_people/models/pb_people.py'
new = stage / 'pb_people.py'
before, after = ast.parse(old.read_text()), ast.parse(new.read_text())


def without_join(tree):
    return ast.dump(ast.Module(body=[n for n in tree.body if not isinstance(n, ast.FunctionDef) or n.name != '_join_date'], type_ignores=[]))


assert without_join(before) == without_join(after), 'Only the joining-date helper may change'
assert old.read_bytes() != new.read_bytes()
backup = Path('/odoo/archives/sudima-bank-check-20261124/pb_people-before.py')
assert not backup.exists(), 'Deployment already attempted; inspect receipt'
shutil.copy2(old, backup)
receipt = {'revision': revision, 'databases': dbs, 'schema_changes': False,
           'custom_trees_verified': len(inventory['modules']), 'file': str(old)}
stopped = False
note('START', 'Use imported hire date in employee drawer; no data/schema/manifest or asset change; full combined inventory checked; ABM untouched')
started = time.monotonic()
try:
    subprocess.run(['systemctl', 'stop', 'odoo-server'], check=True)
    stopped = True
    shutil.copyfile(new, old)
    assert old.read_bytes() == new.read_bytes()
    subprocess.run(['systemctl', 'start', 'odoo-server'], check=True)
    stopped = False
    receipt['restart_seconds'] = round(time.monotonic() - started)
    receipt['status'] = 'DONE'
    note('DONE', f"restart {receipt['restart_seconds']}s; live HTTP, helper and Chrome verification follow")
except BaseException:
    shutil.copyfile(backup, old)
    receipt['status'] = 'FAILED'
    note('FAILED', 'Original Python restored')
    raise
finally:
    if stopped:
        subprocess.run(['systemctl', 'start', 'odoo-server'], check=True)
    (stage / 'receipt.json').write_text(json.dumps(receipt, indent=2))
print(json.dumps(receipt))
