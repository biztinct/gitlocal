"""Build a committed combined custom-addon release against a server inventory."""
import ast, hashlib, io, json, subprocess, sys, tarfile
from pathlib import Path
root = Path(__file__).resolve().parents[1]
inv = json.loads(Path(sys.argv[1]).read_text())
out = Path(sys.argv[2]);out.mkdir(exist_ok=True)
def git(*args):return subprocess.check_output(['git',*args],cwd=root)
head=git('rev-parse','HEAD').decode().strip()
names=sorted(inv['modules'])
assert not git('diff','HEAD','--',*names).strip(), 'Commit addon changes before packaging'
raw=git('archive','--format=tar','HEAD','--',*names)
files={}
with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
 for entry in archive:
  if entry.isfile():files[entry.name]=archive.extractfile(entry).read()
plan={'commit':head,'all_custom':{},'replace':[]}
for n in names:
 h=hashlib.sha256()
 for p,data in sorted(files.items()):
  if p.startswith(n+'/'):
   rel=p[len(n)+1:];h.update(rel.encode()+b'\0'+data+b'\0')
 version=ast.literal_eval(files[n+'/__manifest__.py'].decode())['version']
 digest=h.hexdigest()
 plan['all_custom'][n]={'version':version,'sha256':digest,'before_sha256':inv['modules'][n]['sha256']}
 if digest!=inv['modules'][n]['sha256']:plan['replace'].append(n)
assert not set(plan['replace']) & set(inv['standard'])
with tarfile.open(out/'addons-final.tar.gz','w:gz') as archive:
 for p,data in sorted(files.items()):
  if p.split('/')[0] in plan['replace']:
   entry=tarfile.TarInfo(p);entry.size=len(data);entry.mode=0o644
   archive.addfile(entry,io.BytesIO(data))
(out/'release-final.json').write_text(json.dumps(plan,indent=2))
print(json.dumps({'commit':head,'custom_trees':len(names),'replace':plan['replace']}))
