import json, hashlib, subprocess
from pathlib import Path
root=Path('/odoo/odoo-server/addons')
def run(a):return subprocess.check_output(a,text=True).strip()
def tree(folder):
 h=hashlib.sha256();files={}
 for p in sorted(folder.rglob('*')):
  if p.is_symlink() or not p.is_file() or p.name=='.DS_Store' or any(s in ('__pycache__','.git','node_modules') for s in p.parts) or p.suffix in ('.pyc','.pyo'):continue
  rel=str(p.relative_to(folder));data=p.read_bytes();files[rel]=hashlib.sha256(data).hexdigest();h.update(rel.encode()+b'\0'+data+b'\0')
 return {'sha256':h.hexdigest(),'files':files}
standard={p.split('/')[1] for p in run(['git','-c','safe.directory=/odoo/odoo-server','-C','/odoo/odoo-server','ls-files','--','addons']).splitlines() if p.endswith('/__manifest__.py') and p.count('/')==2}
out={'modules':{p.parent.name:tree(p.parent) for p in root.glob('*/__manifest__.py') if p.parent.name not in standard},'databases':{}}
for db in ('p0clone','payobook_template','payobook','sudima','rize'):
 versions=run(['sudo','-u','postgres','psql','-X','-At','-d',db,'-c',"SELECT name,latest_version FROM ir_module_module WHERE state='installed'"])
 out['databases'][db]=dict(line.split('|',1) for line in versions.splitlines())
print(json.dumps(out))
