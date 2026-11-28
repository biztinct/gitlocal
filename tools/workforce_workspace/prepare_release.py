"""Run only after the other deployment closes; inventory must be freshly captured."""
import ast, hashlib, json, subprocess, tarfile
from pathlib import Path
root=Path('/private/tmp/payobook-workforce-workspace-20261124')
ops=Path('/private/tmp/workforce-workspace-ops-20261124')
before=json.loads((ops/'before.json').read_text())
def tree(folder):
 h=hashlib.sha256();files={}
 for p in sorted(folder.rglob('*')):
  if p.is_symlink() or not p.is_file() or p.name=='.DS_Store' or any(s in ('__pycache__','.git','node_modules') for s in p.parts) or p.suffix in ('.pyc','.pyo'):continue
  rel=str(p.relative_to(folder));data=p.read_bytes();files[rel]=hashlib.sha256(data).hexdigest();h.update(rel.encode()+b'\0'+data+b'\0')
 return h.hexdigest(),files
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
assert head==subprocess.check_output(['git','rev-parse','origin/19.1'],cwd=root,text=True).strip()
assert not subprocess.check_output(['git','status','--porcelain','--','pb_workforce_workspace'],cwd=root,text=True).strip()
plan={'commit':head,'replace':['pb_workforce_workspace'],'all_custom':{},'preserved_runtime_artifacts':[]}
for name in sorted(set(before['modules'])|{'pb_workforce_workspace'}):
 current,files=tree(root/name);old=before['modules'].get(name)
 assert (root/name/'__manifest__.py').exists(),name
 if old and name!='pb_workforce_workspace':
  diff=[p for p in files.keys()|old['files'].keys() if files.get(p)!=old['files'].get(p)]
  assert not diff or (name=='pb_clock' and diff==['releases/PayobookAttendanceConnector.zip']),(name,diff)
  if diff:plan['preserved_runtime_artifacts'].append('pb_clock/releases/PayobookAttendanceConnector.zip: existing Windows release retained')
 version=ast.literal_eval((root/name/'__manifest__.py').read_text())['version']
 plan['all_custom'][name]={'version':version,'before_sha256':old['sha256'] if old else None,'sha256':current if name in plan['replace'] else old['sha256']}
for db,v in before['databases'].items():
 assert all(d in v for d in ast.literal_eval((root/'pb_workforce_workspace/__manifest__.py').read_text())['depends']),db
(ops/'release-final.json').write_text(json.dumps(plan,indent=2))
with tarfile.open(ops/'addons-final.tar.gz','w:gz') as t:
 for name in plan['replace']:t.add(root/name,arcname=name,filter=lambda p:None if '__pycache__' in p.name.split('/') or p.name.endswith(('.pyc','.pyo')) else p)
print('Prepared',head,'combined modules',len(plan['all_custom']))
