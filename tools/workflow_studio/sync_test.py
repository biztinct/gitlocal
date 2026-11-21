#!/usr/bin/env python3
"""Sync only the isolated test overlay, never active addons; run ORM tests."""
import io,subprocess,tarfile,sys
from pathlib import Path
root=Path(__file__).resolve().parents[2]
archive=Path('/tmp/workflow-studio-resume-addons.tar.gz')
with tarfile.open(archive,'w:gz') as t:
    t.add(root/'pb_lifecycle',arcname='pb_lifecycle',filter=lambda x:None if '__pycache__' in x.name or x.name.endswith('.pyc') else x)
subprocess.run(['scp','-q',str(archive),'Payobook19v2:/tmp/workflow-studio-resume-addons.tar.gz'],check=True)
subprocess.run(['scp','-q',str(root/'tools/workflow_studio/run_suite.py'),'Payobook19v2:/tmp/workflow-studio-suite-resume.py'],check=True)
script=r'''
from pathlib import Path
import subprocess,tarfile
root=Path('/tmp/workflow-studio-resume-20261109')
assert (root/'test.conf').exists()
with tarfile.open('/tmp/workflow-studio-resume-addons.tar.gz') as t:t.extractall(root/'addons',filter='data')
(root/'run_suite.py').write_bytes(Path('/tmp/workflow-studio-suite-resume.py').read_bytes())
subprocess.run(['chown','-R','odoo:odoo',str(root)],check=True)
args=['sudo','-u','odoo','python3','/odoo/odoo-server/odoo-bin','-c',str(root/'test.conf'),'--addons-path='+str(root/'addons')+',/odoo/odoo-server/addons']
if UPGRADE:
 with (root/'upgrade-console.log').open('w') as log:
  result=subprocess.run(args+['-u','pb_lifecycle','--no-http','--max-cron-threads=0','--stop-after-init','--logfile='+str(root/'upgrade.log')],stdout=log,stderr=subprocess.STDOUT)
 if result.returncode:
  print((root/'upgrade.log').read_text()[-6000:]);raise SystemExit(1)
with (root/'run_suite.py').open() as script,(root/'tests-output.txt').open('w') as log:
 r=subprocess.run(args[:5]+['shell']+args[5:]+['--no-http','--max-cron-threads=0','--logfile='+str(root/'tests.log')],stdin=script,stdout=log,stderr=subprocess.STDOUT)
output=(root/'tests-output.txt').read_text()
print(output[-22000:])
raise SystemExit(0 if '"successful": true' in output else 1)
'''
subprocess.run(['ssh','Payobook19v2','sudo','python3','-'],input='UPGRADE='+repr('--upgrade' in sys.argv)+'\n'+script,text=True,check=True)
