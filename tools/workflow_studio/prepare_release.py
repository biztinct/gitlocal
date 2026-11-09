#!/usr/bin/env python3
"""Build a committed combined release; refuse unknown concurrent server changes."""
import ast, hashlib, io, json, subprocess, tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
STAGE=Path('/tmp/workflow-studio-release-20261109');STAGE.mkdir(exist_ok=True)
BASE='874f18ac35ef874fdc3136e5258106033e710503'
def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args])
commit=git('rev-parse','HEAD').decode().strip()
assert not git('diff','--name-only').strip(), 'Commit implementation changes first'
remote=r'''
from pathlib import Path
import hashlib,json,subprocess
base=Path('/odoo/odoo-server/addons')
tracked=subprocess.check_output(['git','-c','safe.directory=/odoo/odoo-server','-C','/odoo/odoo-server','ls-files','--','addons'],text=True).splitlines()
standard={p.split('/')[1] for p in tracked if p.count('/')==2 and p.endswith('/__manifest__.py')};standard.add('base')
modules={}
for p in base.iterdir():
 if p.name in standard or not (p/'__manifest__.py').is_file():continue
 files={}
 for f in sorted(p.rglob('*'),key=lambda f:str(f.relative_to(p))):
  if f.is_file() and not f.is_symlink() and '__pycache__' not in f.parts and f.suffix not in ('.pyc','.pyo') and f.name!='.DS_Store':files[str(f.relative_to(p))]=hashlib.sha256(f.read_bytes()).hexdigest()
 h=hashlib.sha256()
 for f in sorted(p.rglob('*'),key=lambda f:str(f.relative_to(p))):
  if str(f.relative_to(p)) in files:h.update(str(f.relative_to(p)).encode()+b'\0'+f.read_bytes()+b'\0')
 modules[p.name]={'files':files,'tree':h.hexdigest()}
print(json.dumps({'standard':sorted(standard),'modules':modules}))
'''
live=json.loads(subprocess.run(['ssh','Payobook19v2','sudo','python3','-'],input=remote,text=True,capture_output=True,check=True).stdout)
modules=[m for m in live['modules'] if (ROOT/m/'__manifest__.py').is_file()]
def archive(rev):
 data={}
 with tarfile.open(fileobj=io.BytesIO(git('archive',rev,'--',*modules))) as t:
  for p in t.getmembers():
   if p.isfile():data[p.name]=t.extractfile(p).read()
 return data
current,previous=archive(commit),archive(BASE)
plan={'commit':commit,'replace':[],'all_custom':{},'server_only_preserved':sorted(set(live['modules'])-set(modules))}
conflicts=[]
for name in modules:
 prefix=name+'/';files={k[len(prefix):]:v for k,v in current.items() if k.startswith(prefix)}
 old={k[len(prefix):]:hashlib.sha256(v).hexdigest() for k,v in previous.items() if k.startswith(prefix)}
 expected={k:hashlib.sha256(v).hexdigest() for k,v in files.items()}
 observed=live['modules'][name]['files']
 for key in set(expected)|set(observed):
  actual=observed.get(key)
  if actual not in (old.get(key),expected.get(key)):conflicts.append(prefix+key)
 tree=hashlib.sha256()
 for key in sorted(files):tree.update(key.encode()+b'\0'+files[key]+b'\0')
 plan['all_custom'][name]={'sha256':tree.hexdigest(),'before_sha256':live['modules'][name]['tree'],
                          'version':ast.literal_eval(files['__manifest__.py'].decode())['version']}
 if observed!=expected:plan['replace'].append(name)
assert not conflicts, 'Unknown concurrent server changes: '+repr(conflicts)
assert all(v['before_sha256']==v['sha256'] for n,v in plan['all_custom'].items() if n not in plan['replace']), 'Unchanged module hashes must agree'
assert 'pb_lifecycle' in plan['replace'], 'No Workflow Studio change to deploy'
assert not set(plan['replace'])&set(live['standard'])
(STAGE/'release.json').write_text(json.dumps(plan,indent=2))
with tarfile.open(STAGE/'addons.tar.gz','w:gz') as t:
 for key,data in current.items():
  if key.split('/')[0] not in plan['replace']:continue
  info=tarfile.TarInfo(key);info.size=len(data);info.mode=0o644;t.addfile(info,io.BytesIO(data))
print(json.dumps({'commit':commit,'replace':plan['replace'],'verified_custom_modules':len(modules),'stage':str(STAGE)},indent=2))
