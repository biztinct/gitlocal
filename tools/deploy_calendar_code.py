"""Follow-up code-only calendar release after the schema upgrade.

Manifest/data/security must match the already upgraded server. Changed Python
is projection logic and tests only; no field or model changes are permitted.
"""
import ast, datetime, fcntl, hashlib, json, os, subprocess, sys, tarfile
from pathlib import Path
stage=Path(sys.argv[1]).resolve();assert str(stage).startswith('/tmp/shared-calendar-')
plan=json.loads((stage/'release-final.json').read_text());addons=Path('/odoo/odoo-server/addons')
lock=open('/tmp/payobook-studio-deploy.lock','a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
notes=Path('/opt/deploy-notes.md');dbs=['p0clone','payobook','payobook_template','rize']
def run(args,**kw):return subprocess.run(args,check=True,**kw)
def sql(db,q):return run(['sudo','-u','postgres','psql','-X','-v','ON_ERROR_STOP=1','-d',db,'-Atc',q],capture_output=True,text=True).stdout.strip()
def tree(folder):
 h=hashlib.sha256()
 for p in sorted(folder.rglob('*')):
  if not p.is_file() or p.is_symlink() or p.name=='.DS_Store' or '__pycache__' in p.parts or p.suffix in ('.pyc','.pyo'):continue
  h.update(str(p.relative_to(folder)).encode()+b'\0'+p.read_bytes()+b'\0')
 return h.hexdigest()
def schema(source):
 tree=ast.parse(source)
 return [(n.name,ast.dump(n.bases[0]) if n.bases else '',[(x.targets[0].id,ast.dump(x.value)) for x in n.body if isinstance(x,ast.Assign) and isinstance(x.targets[0],ast.Name) and (x.targets[0].id.startswith('_') or isinstance(x.value,ast.Call) and isinstance(x.value.func,ast.Attribute) and isinstance(x.value.func.value,ast.Name) and x.value.func.value.id=='fields')]) for n in tree.body if isinstance(n,ast.ClassDef)]
def note(state):
 with notes.open('a') as f:f.write(datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')+' | ChatGPT Calendar follow-up | '+state+' | '+','.join(plan['replace'])+' | '+','.join(dbs)+' | short restart | '+plan['commit']+'; '+str(stage)+'\n')
active={}
for line in notes.read_text().splitlines():
 p=[x.strip() for x in line.split('|')]
 if len(p)!=7:continue
 if p[2]=='START':active[p[1]]=line
 elif p[2] in ('DONE','FAILED'):active.pop(p[1],None)
assert not active,active
assert set(plan['replace'])<= {'pb_hiring'}, 'Only reviewed calendar code in this follow-up'
for n,v in plan['all_custom'].items():assert tree(addons/n)==v['before_sha256'],n
for db in dbs:
 versions=dict(x.split('|',1) for x in sql(db,"SELECT name,latest_version FROM ir_module_module WHERE state='installed'").splitlines())
 for n,v in plan['all_custom'].items():
  if n in versions:assert versions[n].removeprefix('19.0.')==v['version'].removeprefix('19.0.'),(db,n)
release=stage/'release';release.mkdir(exist_ok=True)
with tarfile.open(stage/'addons-final.tar.gz') as t:
 for m in t:
  assert Path(m.name).parts[0] in plan['replace'] and not m.name.startswith('/') and '..' not in Path(m.name).parts and not m.issym() and not m.islnk()
 t.extractall(release,filter='data')
for n in plan['replace']:
 for p in (release/n).rglob('*'):
  if not p.is_file():continue
  rel=p.relative_to(release/n);prior=addons/n/rel
  if not prior.exists() or p.read_bytes()!=prior.read_bytes():
   assert str(rel).startswith(('static/','tests/')) or str(rel)=='models/shared_calendar.py',rel
   if str(rel)=='models/shared_calendar.py':assert schema(p.read_text())==schema(prior.read_text()),'Schema change requires upgrade'
backup=stage/'code-before.tar.gz'
with tarfile.open(backup,'w:gz') as t:
 for n in plan['replace']:t.add(addons/n,arcname=n)
receipt={'commit':plan['commit'],'databases':dbs,'custom_trees':len(plan['all_custom']),'schema_changes':False};stopped=False
note('START')
try:
 run(['systemctl','stop','odoo-server']);stopped=True
 for n in plan['replace']:
  run(['rsync','-a','--delete',str(release/n)+'/',str(addons/n)+'/']);run(['chown','-R','odoo:odoo',str(addons/n)])
 for n,v in plan['all_custom'].items():assert tree(addons/n)==v['sha256'],n
 for db in dbs:
  sql(db,"INSERT INTO orm_signaling_assets DEFAULT VALUES; DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'; INSERT INTO ir_config_parameter(key,value) VALUES ('web.assets.version','"+plan['commit']+"') ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value")
 run(['systemctl','start','odoo-server']);stopped=False
 receipt['status']='DONE';note('DONE')
except BaseException:
 restore=stage/'restore';restore.mkdir(exist_ok=True)
 with tarfile.open(backup) as t:t.extractall(restore,filter='data')
 for n in plan['replace']:run(['rsync','-a','--delete',str(restore/n)+'/',str(addons/n)+'/'])
 receipt['status']='FAILED';note('FAILED');raise
finally:
 if stopped:run(['systemctl','start','odoo-server'])
 (stage/'receipt.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt))
