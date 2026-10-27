import datetime,hashlib,json,os,pwd,re,subprocess,tarfile,time
from pathlib import Path
import sys,fcntl
stage=Path(sys.argv[1]).resolve()
assert str(stage).startswith('/tmp/access-studio-')
lock=open('/tmp/payobook-studio-deploy.lock','a+')
fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
plan=json.loads((stage/'release-final.json').read_text())
addons=Path('/odoo/odoo-server/addons'); notes=Path('/opt/deploy-notes.md')
dbs=['p0clone','payobook','payobook_template','rize']
receipt={'commit':plan['commit'],'status':'preflight','databases':{}}
def run(args,**kw):return subprocess.run(args,check=True,**kw)
def sql(db,q):return run(['sudo','-u','postgres','psql','-X','-v','ON_ERROR_STOP=1','-d',db,'-Atc',q],capture_output=True,text=True).stdout.strip()
def entry(state,note):
 now=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
 with notes.open('a') as f:f.write(f'{now} | ChatGPT Access Studio | {state} | '+','.join(plan['replace'])+' | '+','.join(dbs)+' | '+str(receipt.get('downtime_seconds','pending'))+' seconds | '+note+'\n')
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
 if len(p)!=7:continue
 if p[2]=='START':active[p[1]]=line
 elif p[2] in ('DONE','FAILED'):active.pop(p[1],None)
assert not active,active
assert run(['systemctl','is-active','odoo-server'],capture_output=True,text=True).stdout.strip()=='active'
tracked=run(['git','-c','safe.directory=/odoo/odoo-server','-C','/odoo/odoo-server','ls-files','--','addons'],capture_output=True,text=True).stdout.splitlines()
standard={p.split('/')[1] for p in tracked if p.endswith('/__manifest__.py') and p.count('/')==2}
assert not set(plan['replace'])&standard
for n,v in plan['all_custom'].items():assert tree(addons/n)==v['before_sha256'], 'Concurrent change: '+n
for db in dbs:
 assert not sql(db,"SELECT name FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove')")
 versions=dict(r.split('|',1) for r in sql(db,"SELECT name,latest_version FROM ir_module_module WHERE state='installed'").splitlines())
 ids=[int(i) for i in sql(db,'SELECT id FROM ir_cron WHERE active ORDER BY id').splitlines()]
 receipt['databases'][db]={'prior_crons':list(ids),'crons':ids,'upgrade_modules':[n for n,v in plan['all_custom'].items() if n in versions and (n in plan['replace'] or norm(v['version'])!=norm(versions[n]))]}
label=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
backup=Path('/odoo/backups')/('access-studio-'+label);backup.mkdir(mode=0o700)
permanent=Path('/odoo/archives')/('rize-access-studio-'+label);permanent.mkdir(mode=0o700)
(backup/'retention.json').write_text(json.dumps({'days':7,'preserve_latest_usable':True,'databases':dbs[:-1]}))
(permanent/'retention.json').write_text(json.dumps({'permanent':True,'never_auto_delete':True,'database':'rize'}))
logs=stage/'deploy-logs';logs.mkdir(exist_ok=True);odoo=pwd.getpwnam('odoo');os.chown(logs,odoo.pw_uid,odoo.pw_gid)
entry('START','Approved Access Studio Option 1; combined commit '+plan['commit']+'. Backup all active DBs; Rize permanent; preserve cron states. No ABM.')
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
  for n in plan['replace']:t.add(addons/n,arcname=n,filter=lambda p:None if '__pycache__' in p.name.split('/') or p.name.endswith(('.pyc','.pyo')) else p)
 dest=stage/'release';dest.mkdir(exist_ok=True)
 with tarfile.open(stage/'addons-final.tar.gz') as t:
  for m in t.getmembers():assert Path(m.name).parts[0] in plan['replace'] and not m.name.startswith('/') and '..' not in Path(m.name).parts and not m.issym() and not m.islnk()
  t.extractall(dest,filter='data')
 for n in plan['replace']:
  run(['rsync','-a','--delete',str(dest/n)+'/',str(addons/n)+'/']);run(['chown','-R','odoo:odoo',str(addons/n)])
 for n,v in plan['all_custom'].items():assert tree(addons/n)==v['sha256'],n
 for db in dbs:
  mods=receipt['databases'][db]['upgrade_modules']
  if mods:
   sql(db,'UPDATE ir_cron SET active=false WHERE active')
   with (logs/(db+'-console.log')).open('w') as f:
    run(['sudo','-u','odoo','python3','/odoo/odoo-server/odoo-bin','-c','/etc/odoo-server.conf','-d',db,'-u',','.join(mods),'--no-http','--max-cron-threads=0','--stop-after-init','--logfile='+str(logs/(db+'-upgrade.log'))],stdout=f,stderr=subprocess.STDOUT)
  studio_cron=sql(db,"SELECT res_id FROM ir_model_data WHERE module='biz_access' AND name='cron_studio_expire' AND model='ir.cron'")
  if studio_cron and int(studio_cron) not in receipt['databases'][db]['crons']:receipt['databases'][db]['crons'].append(int(studio_cron));receipt['databases'][db]['crons'].sort()
  receipt['databases'][db]['upgraded']=True;print('UPGRADED',db,flush=True)
  if db=='p0clone':
   tags='/biz_access:TestAccessStudio'
   with (stage/'run_suite.py').open() as source,(logs/'p0clone-tests-output.txt').open('w') as f:
    run(['sudo','-u','odoo','env','STUDIO_TEST_TAGS='+tags,'python3','/odoo/odoo-server/odoo-bin','shell','-c','/etc/odoo-server.conf','-d',db,'--workers=0','--max-cron-threads=0','--http-interface=127.0.0.1','--http-port=18399','--gevent-port=18398','--db-filter=p0clone','--logfile='+str(logs/'p0clone-tests.log')],stdin=source,stdout=f,stderr=subprocess.STDOUT)
   line=next(x for x in (logs/'p0clone-tests-output.txt').read_text().splitlines() if x.startswith('STUDIO_TEST_RESULT='))
   result=json.loads(line.split('=',1)[1]);assert result['successful'] and result['tests']>=31,result
   receipt['p0clone_tests']=result;print('P0CLONE_TESTS',result,flush=True)
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
 for host in ['payobook.com','rize.payobook.com','p0clone.payobook.com']:
  for attempt in range(8):
   code=run(['curl','-L','-sS','--max-time','30','-o','/dev/null','-w','%{http_code}','https://'+host+'/web/login'],capture_output=True,text=True).stdout.strip()
   if code=='200':break
   time.sleep(2)
  assert code=='200',(host,code)
  receipt.setdefault('http',{})[host]=code
 for n,v in plan['all_custom'].items():assert tree(addons/n)==v['sha256'],n
 receipt['status']='DONE';entry('DONE','All combined custom trees and installed versions verified; p0clone regression passed; cron states restored; sites HTTP 200. Evidence '+str(stage))
except BaseException as exc:
 receipt['status']='FAILED';receipt['error']=type(exc).__name__+': '+str(exc)
 entry('FAILED','Release stopped at failed step; inspect receipt; backups retained; no automatic destructive database restore. '+receipt['error'])
 raise
finally:
 if stopped:
  # The schema additions are backward compatible and seed no grants. If an
  # upgrade fails before service restart, restore only our backed-up addon
  # trees, preserve databases for diagnosis, and restore the prior cron set.
  if receipt['status']=='FAILED' and (backup/'custom-before.tar.gz').exists():
   restore=stage/'restore-before';restore.mkdir(exist_ok=True)
   with tarfile.open(backup/'custom-before.tar.gz') as t:t.extractall(restore,filter='data')
   for n in plan['replace']:
    run(['rsync','-a','--delete',str(restore/n)+'/',str(addons/n)+'/'])
    run(['chown','-R','odoo:odoo',str(addons/n)])
   receipt['code_restored']=True
  for db in dbs:
   ids=receipt['databases'][db]['prior_crons'];sql(db,'UPDATE ir_cron SET active=false WHERE active')
   if ids:sql(db,'UPDATE ir_cron SET active=true WHERE id IN ('+','.join(map(str,ids))+')')
  run(['systemctl','start','odoo-server'])
 (stage/'receipt.json').write_text(json.dumps(receipt,indent=2));(stage/'sentinel').write_text(receipt['status'])
