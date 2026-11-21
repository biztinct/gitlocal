#!/usr/bin/env python3
"""Read-only check of committed custom content and installed versions in active DBs."""
import ast
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[3]
DATABASES = ['payobook', 'payobook_template', 'p0clone', 'rize']
REMOTE = r'''
import hashlib,json,subprocess
from pathlib import Path
base=Path('/odoo/odoo-server/addons')
def run(args):return subprocess.run(args,check=True,capture_output=True,text=True).stdout
standard={p.split('/')[1] for p in run(['git','-c','safe.directory=/odoo/odoo-server','-C','/odoo/odoo-server','ls-files','addons']).splitlines() if p.count('/')>=2}
standard.add('base')  # Odoo core lives under odoo/addons/base, not the deployment addons directory.
versions={}
for db in DATABASES:
 versions[db]=dict(x.split('|',1) for x in run(['sudo','-u','postgres','psql','-X','-At','-d',db,'-c',"select name,latest_version from ir_module_module where state='installed'"]).splitlines())
modules=sorted(p.name for p in base.iterdir() if p.name not in standard and (p/'__manifest__.py').is_file())
hashes={}
for module in modules:
 for p in (base/module).rglob('*'):
  if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pyo') and p.name!='.DS_Store':hashes[str(p.relative_to(base))]=hashlib.sha256(p.read_bytes()).hexdigest()
print(json.dumps({'standard':sorted(standard),'modules':modules,'versions':versions,'hashes':hashes}))
'''
def verify():
    live=json.loads(subprocess.run(['ssh','Payobook19v2','sudo','python3','-'],input='DATABASES='+repr(DATABASES)+'\n'+REMOTE,capture_output=True,text=True,check=True).stdout)
    commit=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
    modules=[m for m in live['modules'] if (ROOT/m/'__manifest__.py').exists()]
    archive=subprocess.check_output(['git','-C',str(ROOT),'archive',commit,'--',*modules])
    hashes={};versions={}
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar.getmembers():
            if not member.isfile():continue
            content=tar.extractfile(member).read();hashes[member.name]=hashlib.sha256(content).hexdigest()
            if member.name.count('/')==1 and member.name.endswith('/__manifest__.py'):versions[member.name.split('/')[0]]=ast.literal_eval(content.decode())['version']
    def norm(value):return value[5:] if value.startswith('19.0.') else value
    mismatch={db:[m for m,v in versions.items() if m in installed and norm(v)!=norm(installed[m])] for db,installed in live['versions'].items()}
    changed=[p for p,h in hashes.items() if live['hashes'].get(p)!=h]
    extra=[p for p in set(live['hashes'])-set(hashes) if p.split('/')[0] in modules]
    installed_custom=set().union(*(set(v) for v in live['versions'].values()))-set(live['standard'])
    missing=sorted(installed_custom-set(modules))
    result={'combined_commit':commit,'server':'Payobook19v2','addons':'/odoo/odoo-server/addons','databases':DATABASES,'modules':len(modules),'files':len(hashes),'changed_files':sorted(changed),'extra_server_files':sorted(extra),'installed_custom_missing_locally':missing,'version_mismatches':mismatch,'server_only_modules_preserved':sorted(set(live['modules'])-set(modules))}
    print(json.dumps(result,indent=2))
    if changed or extra or missing or any(mismatch.values()):raise SystemExit('Combined repository/live verification failed; review before deploying.')
    return result
if __name__=='__main__':verify()
