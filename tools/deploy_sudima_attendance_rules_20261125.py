import datetime,hashlib,json,os,pwd,re,subprocess,tarfile,time
from pathlib import Path
import sys,fcntl
stage=Path(sys.argv[1]).resolve()
assert str(stage).startswith('/tmp/sudima-attendance-release-')
lock=open('/tmp/payobook-studio-deploy.lock','a+')
fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
plan=json.loads((stage/'release-final.json').read_text())
addons=Path('/odoo/odoo-server/addons'); notes=Path('/opt/deploy-notes.md')
dbs=['p0clone','payobook_template','payobook','sudima','rize']
receipt={'commit':plan['commit'],'status':'preflight','databases':{}}
def run(args,**kw):return subprocess.run(args,check=True,**kw)
def sql(db,q):return run(['sudo','-u','postgres','psql','-X','-v','ON_ERROR_STOP=1','-d',db,'-Atc',q],capture_output=True,text=True).stdout.strip()
def entry(state,note):
 now=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
 with notes.open('a') as f:f.write(f'{now} | Codex Attendance Rules | {state} | '+','.join(plan['replace'])+' | '+','.join(dbs)+' | '+str(receipt.get('downtime_seconds','pending'))+' seconds | '+note+'\n')
def norm(v):
 p=v.split('.');return '.'.join(p[2:]) if len(p)==5 and p[0]=='19' else v
def tree(folder):
 h=hashlib.sha256()
 for p in sorted(folder.rglob('*')):
  if p.is_symlink() or not p.is_file() or p.name=='.DS_Store' or any(s in ('__pycache__','.git','node_modules') for s in p.parts) or p.suffix in ('.pyc','.pyo'):continue
  h.update(str(p.relative_to(folder)).encode()+b'\0'+p.read_bytes()+b'\0')
 return h.hexdigest()
active={}
for line in notes.read_text().splitlines():
 p=[s.strip() for s in line.split('|')]
 if len(p)<3:continue
 key=re.sub(r"\s*\(.*", "", p[1])
 if p[2]=='START':active[key]=line
 elif p[2].startswith(('DONE','FAILED','DATA DONE','TEST DONE','DEPLOYED','VERIFIED','ABORTED','CANCELLED','COMPLETE','CALLED OFF')):active.pop(key,None)
assert not active,active
assert run(['systemctl','is-active','odoo-server'],capture_output=True,text=True).stdout.strip()=='active'
tracked=run(['git','-c','safe.directory=/odoo/odoo-server','-C','/odoo/odoo-server','ls-files','--','addons'],capture_output=True,text=True).stdout.splitlines()
standard={p.split('/')[1] for p in tracked if p.endswith('/__manifest__.py') and p.count('/')==2}
assert not set(plan['replace'])&standard
for n,v in plan['all_custom'].items():
 assert (tree(addons/n) if (addons/n).exists() else None)==v['before_sha256'], 'Concurrent change: '+n
for db in dbs:
 assert not sql(db,"SELECT name FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove')")
 versions=dict(r.split('|',1) for r in sql(db,"SELECT name,latest_version FROM ir_module_module WHERE state='installed'").splitlines())
 ids=[int(i) for i in sql(db,'SELECT id FROM ir_cron WHERE active ORDER BY id').splitlines()]
 receipt['databases'][db]={'prior_crons':list(ids),'crons':ids,'upgrade_modules':[n for n,v in plan['all_custom'].items() if n in versions and (n in plan['replace'] or norm(v['version'])!=norm(versions[n]))], 'install_modules':[]}
label=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
backup=Path('/odoo/backups')/('attendance-rules-'+label);backup.mkdir(mode=0o700)
permanent=Path('/odoo/archives')/('rize-attendance-rules-'+label);permanent.mkdir(mode=0o700)
(backup/'retention.json').write_text(json.dumps({'days':7,'preserve_latest_usable':True,'databases':dbs[:-1]}))
(permanent/'retention.json').write_text(json.dumps({'permanent':True,'never_auto_delete':True,'database':'rize'}))
logs=stage/'deploy-logs';logs.mkdir(exist_ok=True);odoo=pwd.getpwnam('odoo');os.chown(logs,odoo.pw_uid,odoo.pw_gid)
entry('START','Paid grace, second unpaid break and late-day payroll source; defaults preserve existing behavior; combined commit '+plan['commit']+'. Backup all active DBs; Rize permanent; preserve cron states. No ABM.')
stopped=False
try:
 run(['systemctl','stop','odoo-server']);stopped=True;start=time.monotonic()
 for db in dbs:
  dest=permanent if db=='rize' else backup/db;dest.mkdir(mode=0o700,exist_ok=True)
  with (dest/(db+'.dump')).open('xb') as f:run(['sudo','-u','postgres','pg_dump','-Fc',db],stdout=f)
  run(['pg_restore','--list',str(dest/(db+'.dump'))],stdout=subprocess.DEVNULL)
  fs=Path('/odoo/.local/share/Odoo/filestore')/db
  if fs.is_dir():run(['cp','-al',str(fs),str(dest/'filestore')])
  receipt['databases'][db]['backup']=str(dest);print('BACKUP',db,flush=True)
 with tarfile.open(backup/'custom-before.tar.gz','w:gz') as t:
  for n in plan['replace']:
   if not (addons/n).exists():continue
   t.add(addons/n,arcname=n,filter=lambda p:None if '__pycache__' in p.name.split('/') or p.name.endswith(('.pyc','.pyo')) else p)
 dest=stage/'release';dest.mkdir(exist_ok=True)
 with tarfile.open(stage/'addons-final.tar.gz') as t:
  for m in t.getmembers():assert Path(m.name).parts[0] in plan['replace'] and not m.name.startswith('/') and '..' not in Path(m.name).parts and not m.issym() and not m.islnk()
  t.extractall(dest,filter='data')
 for n in plan['replace']:
  run(['rsync','-a','--delete',str(dest/n)+'/',str(addons/n)+'/']);run(['chown','-R','odoo:odoo',str(addons/n)])
 for n,v in plan['all_custom'].items():assert tree(addons/n)==v['sha256'],n
 for db in dbs:
  mods=receipt['databases'][db]['upgrade_modules']; ins=receipt['databases'][db]['install_modules']
  if mods or ins:
   sql(db,'UPDATE ir_cron SET active=false WHERE active')
   with (logs/(db+'-console.log')).open('w') as f:
    run(['sudo','-u','odoo','python3','/odoo/odoo-server/odoo-bin','-c','/etc/odoo-server.conf','-d',db,*(['-u',','.join(mods)] if mods else []),*(['-i',','.join(ins)] if ins else []),'--no-http','--max-cron-threads=0','--stop-after-init','--logfile='+str(logs/(db+'-upgrade.log'))],stdout=f,stderr=subprocess.STDOUT)
  receipt['databases'][db]['upgraded']=True;print('UPGRADED',db,flush=True)
 for db in dbs:
  ids=receipt['databases'][db]['crons'];sql(db,'UPDATE ir_cron SET active=false WHERE active')
  if ids:sql(db,'UPDATE ir_cron SET active=true WHERE id IN ('+','.join(map(str,ids))+')')
  assert [int(i) for i in sql(db,'SELECT id FROM ir_cron WHERE active ORDER BY id').splitlines()]==ids
  versions=dict(r.split('|',1) for r in sql(db,"SELECT name,latest_version FROM ir_module_module WHERE state='installed'").splitlines())
  assert all(norm(versions[n])==norm(v['version']) for n,v in plan['all_custom'].items() if n in versions)
  receipt['databases'][db]['versions_verified']=True

 for db in dbs:
  sql(db, "INSERT INTO orm_signaling_assets DEFAULT VALUES; DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'; INSERT INTO ir_config_parameter(key,value) VALUES ('web.assets.version','"+plan['commit']+"') ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value")
 run(['systemctl','start','odoo-server']);stopped=False;receipt['downtime_seconds']=round(time.monotonic()-start)
 for host in ['payobook.com','rize.payobook.com','p0clone.payobook.com','sudima.payobook.com']:
  for attempt in range(8):
   code=run(['curl','-L','-sS','--max-time','30','-o','/dev/null','-w','%{http_code}','https://'+host+'/web/login'],capture_output=True,text=True).stdout.strip()
   if code=='200':break
   time.sleep(2)
  assert code=='200',(host,code)
  receipt.setdefault('http',{})[host]=code
 for n,v in plan['all_custom'].items():assert tree(addons/n)==v['sha256'],n
 receipt['status']='DONE';entry('DONE','All combined custom trees and installed versions verified; cron states restored; sites HTTP 200. Evidence '+str(stage))
except BaseException as exc:
 receipt['status']='FAILED';receipt['error']=type(exc).__name__+': '+str(exc)
 entry('FAILED','Release stopped at failed step; inspect receipt; backups retained; failed pre-restart upgrades restore the exact stopped-service snapshots. '+receipt['error'])
 raise
finally:
 if stopped:
  if receipt['status']=='FAILED' and (backup/'custom-before.tar.gz').exists():
   restore=stage/'restore-before';restore.mkdir(exist_ok=True)
   with tarfile.open(backup/'custom-before.tar.gz') as t:t.extractall(restore,filter='data')
   for n in plan['replace']:
    if not (restore/n).exists():
     import shutil
     assert n=='pb_workforce_workspace' and plan['all_custom'][n]['before_sha256'] is None
     shutil.rmtree(addons/n)
     continue
    run(['rsync','-a','--delete',str(restore/n)+'/',str(addons/n)+'/'])
    run(['chown','-R','odoo:odoo',str(addons/n)])
   for db,info in receipt['databases'].items():
    if 'backup' not in info:continue
    # The service has remained stopped since this snapshot; restore both
    # schema and data so old code never runs against a partially upgraded view.
    run(['pg_restore','--list',str(Path(info['backup'])/(db+'.dump'))],stdout=subprocess.DEVNULL)
    sql('postgres', "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='"+db+"' AND pid<>pg_backend_pid()")
    run(['sudo','-u','postgres','dropdb',db])
    run(['sudo','-u','postgres','createdb','-O','odoo',db])
    with (Path(info['backup'])/(db+'.dump')).open('rb') as snapshot:
     run(['sudo','-u','postgres','pg_restore','--exit-on-error','--no-owner','--role=odoo','-d',db],stdin=snapshot)
   receipt['code_and_databases_restored']=True
  for db in dbs:
   ids=receipt['databases'][db]['prior_crons'];sql(db,'UPDATE ir_cron SET active=false WHERE active')
   if ids:sql(db,'UPDATE ir_cron SET active=true WHERE id IN ('+','.join(map(str,ids))+')')
  run(['systemctl','start','odoo-server'])
 (stage/'receipt.json').write_text(json.dumps(receipt,indent=2));(stage/'sentinel').write_text(receipt['status'])
