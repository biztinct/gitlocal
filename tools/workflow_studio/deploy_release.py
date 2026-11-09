"""Server release entry, with full backups, concurrency checks and cron retention."""
import datetime,fcntl,hashlib,json,os,pwd,subprocess,sys,tarfile,time
from pathlib import Path
stage=Path(sys.argv[1]).resolve();assert stage==Path('/tmp/workflow-studio-release-20261109')
plan=json.loads((stage/'release.json').read_text());addons=Path('/odoo/odoo-server/addons')
lock=(Path('/tmp')/'payobook-studio-deploy.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
notes=Path('/opt/deploy-notes.md');dbs=['p0clone','payobook','payobook_template','rize']
receipt={'commit':plan['commit'],'status':'preflight','databases':{}}
def run(args,**kw):return subprocess.run(args,check=True,**kw)
def sql(db,q):return run(['sudo','-u','postgres','psql','-X','-v','ON_ERROR_STOP=1','-d',db,'-Atc',q],capture_output=True,text=True).stdout.strip()
def norm(v):return v[5:] if v.startswith('19.0.') else v
def tree(folder):
 h=hashlib.sha256()
 for p in sorted(folder.rglob('*')):
  if p.is_symlink() or not p.is_file() or p.name=='.DS_Store' or '__pycache__' in p.parts or p.suffix in ('.pyc','.pyo'):continue
  h.update(str(p.relative_to(folder)).encode()+b'\0'+p.read_bytes()+b'\0')
 return h.hexdigest()
def entry(state,text):
 with notes.open('a') as f:f.write(datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')+' | ChatGPT Workflow Studio | '+state+' | '+','.join(plan['replace'])+' | '+','.join(dbs)+' | '+str(receipt.get('downtime_seconds','pending'))+' seconds | '+text+'\n')
active={}
for line in notes.read_text().splitlines():
 p=[x.strip() for x in line.split('|')]
 if len(p)<3:continue
 name=p[1].split(' (',1)[0]
 if p[2]=='START':active[name]=line
 elif p[2].endswith(('DONE','FAILED')):active.pop(name,None)
assert not active,active
assert run(['systemctl','is-active','odoo-server'],capture_output=True,text=True).stdout.strip()=='active'
tracked=run(['git','-c','safe.directory=/odoo/odoo-server','-C','/odoo/odoo-server','ls-files','--','addons'],capture_output=True,text=True).stdout.splitlines()
standard={p.split('/')[1] for p in tracked if p.count('/')==2 and p.endswith('/__manifest__.py')}
assert not set(plan['replace'])&standard
assert (addons/'base_automation/__manifest__.py').is_file()
for n,v in plan['all_custom'].items():assert tree(addons/n)==v['before_sha256'],'Concurrent server change: '+n
for db in dbs:
 assert not sql(db,"SELECT name FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove')")
 versions=dict(x.split('|',1) for x in sql(db,"SELECT name,latest_version FROM ir_module_module WHERE state='installed'").splitlines())
 crons=[int(x) for x in sql(db,'SELECT id FROM ir_cron WHERE active ORDER BY id').splitlines()]
 receipt['databases'][db]={'prior_crons':crons,'crons':list(crons),'automation_was_installed':'base_automation' in versions,
   'upgrade_modules':[n for n,v in plan['all_custom'].items() if n in versions and (n in plan['replace'] or norm(versions[n])!=norm(v['version']))],
   'native_counts':{t:int(sql(db,'SELECT count(*) FROM '+t)) for t in ('pb_journey_case','biz_approval_request','hr_employee')}}
label=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
backup=Path('/odoo/backups')/('workflow-studio-'+label);backup.mkdir(mode=0o700)
permanent=Path('/odoo/archives')/('rize-workflow-studio-'+label);permanent.mkdir(mode=0o700)
(backup/'retention.json').write_text(json.dumps({'days':7,'preserve_latest_usable':True,'databases':dbs[:-1]}))
(permanent/'retention.json').write_text(json.dumps({'permanent':True,'never_auto_delete':True,'database':'rize'}))
logs=stage/'logs';logs.mkdir(exist_ok=True);owner=pwd.getpwnam('odoo');os.chown(logs,owner.pw_uid,owner.pw_gid)
entry('START','Owner-authorized system-wide workflow implementation; combined '+plan['commit']+'. Stock Community base_automation; no business flows activated; ABM untouched.')
stopped=False
try:
 run(['systemctl','stop','odoo-server']);stopped=True;start=time.monotonic()
 for db in dbs:
  receipt['databases'][db]['native_counts']={t:int(sql(db,'SELECT count(*) FROM '+t)) for t in ('pb_journey_case','biz_approval_request','hr_employee')}
  dest=permanent if db=='rize' else backup/db;dest.mkdir(mode=0o700,exist_ok=True)
  with (dest/(db+'.dump')).open('xb') as f:run(['sudo','-u','postgres','pg_dump','-Fc',db],stdout=f)
  run(['pg_restore','--list',str(dest/(db+'.dump'))],stdout=subprocess.DEVNULL)
  fs=Path('/odoo/.local/share/Odoo/filestore')/db
  if fs.is_dir():run(['cp','-al',str(fs),str(dest/'filestore')])
  receipt['databases'][db]['backup']=str(dest);print('BACKUP',db,flush=True)
 with tarfile.open(backup/'custom-before.tar.gz','w:gz') as t:
  for n in plan['replace']:t.add(addons/n,arcname=n,filter=lambda x:None if '__pycache__' in x.name or x.name.endswith('.pyc') else x)
 extracted=stage/'release';extracted.mkdir(exist_ok=True)
 with tarfile.open(stage/'addons.tar.gz') as t:
  for item in t.getmembers():assert not item.name.startswith('/') and '..' not in Path(item.name).parts and Path(item.name).parts[0] in plan['replace'] and not item.issym() and not item.islnk()
  t.extractall(extracted,filter='data')
 for n in plan['replace']:
  run(['rsync','-a','--delete',str(extracted/n)+'/',str(addons/n)+'/']);run(['chown','-R','odoo:odoo',str(addons/n)])
 for n,v in plan['all_custom'].items():assert tree(addons/n)==v['sha256'],n
 for db in dbs:
  info=receipt['databases'][db];mods=info['upgrade_modules']
  sql(db,'UPDATE ir_cron SET active=false WHERE active')
  if mods:
   args=['sudo','-u','odoo','python3','/odoo/odoo-server/odoo-bin','-c','/etc/odoo-server.conf','-d',db,'-u',','.join(mods),'--no-http','--max-cron-threads=0','--stop-after-init','--logfile='+str(logs/(db+'-upgrade.log'))]
   if 'pb_lifecycle' in mods and not info['automation_was_installed']:args+=['-i','base_automation']
   with (logs/(db+'-console.txt')).open('w') as f:run(args,stdout=f,stderr=subprocess.STDOUT)
  for t,before in info['native_counts'].items():assert int(sql(db,'SELECT count(*) FROM '+t))==before,(db,t,'Existing records changed during upgrade')
  info['native_counts_preserved']=True
  if 'pb_lifecycle' in mods:
   new_crons=sql(db,"SELECT res_id FROM ir_model_data WHERE model='ir.cron' AND ((module='pb_lifecycle' AND name='cron_workflow_progress')"+(" OR module='base_automation'" if not info['automation_was_installed'] else '')+")")
   info['crons']=sorted(set(info['crons'])|{int(x) for x in new_crons.splitlines()})
   assert sql(db,"SELECT state FROM ir_module_module WHERE name='base_automation'")=='installed'
   assert sql(db,'SELECT count(*) FROM pb_workflow WHERE enabled')=='0','No live workflow is activated by installation'
  info['upgraded']=True;print('UPGRADED',db,flush=True)
  if db=='p0clone':
   with (stage/'run_suite.py').open() as source,(logs/'p0clone-tests.txt').open('w') as out:
    run(['sudo','-u','odoo','python3','/odoo/odoo-server/odoo-bin','shell','-c','/etc/odoo-server.conf','-d',db,'--no-http','--max-cron-threads=0','--logfile='+str(logs/'p0clone-tests.log')],stdin=source,stdout=out,stderr=subprocess.STDOUT)
   line=next(x for x in (logs/'p0clone-tests.txt').read_text().splitlines() if x.startswith('WORKFLOW_TEST_RESULT='))
   result=json.loads(line.split('=',1)[1]);assert result['successful'] and result['tests']>=25,result
   receipt['p0clone_tests']=result;print('P0CLONE_TESTS',result,flush=True)
 for db in dbs:
  info=receipt['databases'][db];sql(db,'UPDATE ir_cron SET active=false WHERE active')
  if info['crons']:sql(db,'UPDATE ir_cron SET active=true WHERE id IN ('+','.join(map(str,info['crons']))+')')
  assert [int(x) for x in sql(db,'SELECT id FROM ir_cron WHERE active ORDER BY id').splitlines()]==info['crons']
  versions=dict(x.split('|',1) for x in sql(db,"SELECT name,latest_version FROM ir_module_module WHERE state='installed'").splitlines())
  assert all(norm(versions[n])==norm(v['version']) for n,v in plan['all_custom'].items() if n in versions)
  info['versions_verified']=True
  sql(db,"INSERT INTO orm_signaling_assets DEFAULT VALUES; DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'; INSERT INTO ir_config_parameter(key,value) VALUES ('web.assets.version','"+plan['commit']+"') ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value")
 run(['systemctl','start','odoo-server']);stopped=False;receipt['downtime_seconds']=round(time.monotonic()-start)
 for host in ['payobook.com','p0clone.payobook.com','rize.payobook.com']:
  for attempt in range(10):
   code=run(['curl','-L','-sS','--max-time','25','-o','/dev/null','-w','%{http_code}','https://'+host+'/web/login'],capture_output=True,text=True).stdout.strip()
   if code=='200':break
   time.sleep(2)
  assert code=='200',(host,code)
  receipt.setdefault('http',{})[host]=code
 for n,v in plan['all_custom'].items():assert tree(addons/n)==v['sha256'],n
 receipt['status']='DONE';entry('DONE','Combined custom content and versions verified in all four DBs; native records retained; p0clone transactional tests passed; cron states preserved plus new workflow/native trigger workers. Browser validation follows.')
except BaseException as exc:
 receipt['status']='FAILED';receipt['error']=str(exc);entry('FAILED','Inspect '+str(stage)+'; backups retained. '+str(exc));raise
finally:
 if stopped:
  if (backup/'custom-before.tar.gz').exists():
   restore=stage/'restore-before';restore.mkdir(exist_ok=True)
   with tarfile.open(backup/'custom-before.tar.gz') as t:t.extractall(restore,filter='data')
   for n in plan['replace']:
    run(['rsync','-a','--delete',str(restore/n)+'/',str(addons/n)+'/']);run(['chown','-R','odoo:odoo',str(addons/n)])
   receipt['code_restored']=True
  for db in dbs:
   ids=receipt['databases'][db]['prior_crons'];sql(db,'UPDATE ir_cron SET active=false WHERE active')
   if ids:sql(db,'UPDATE ir_cron SET active=true WHERE id IN ('+','.join(map(str,ids))+')')
  run(['systemctl','start','odoo-server'])
 (stage/'receipt.json').write_text(json.dumps(receipt,indent=2))
print('WORKFLOW_RELEASE_RESULT='+receipt['status'])
