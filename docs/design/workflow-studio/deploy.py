#!/usr/bin/env python3
"""Deploy the committed, standalone preview to payobook.com, without Odoo writes. Only the design artifact is in scope."""
import hashlib
import pathlib
import subprocess
import json

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
HOST = "Payobook19v2"
head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                      capture_output=True, text=True, check=True).stdout.strip()
paths = [HERE.parent / "workflow-studio-poc.html", HERE / "nginx-location.conf"]
sources = [p for p in HERE.iterdir() if p.is_file() and p.suffix in ('.js', '.css', '.html', '.py', '.cjs', '.txt', '.woff2')]
for path in paths + sources:
    rel = str(path.relative_to(ROOT))
    committed = subprocess.run(["git", "-C", str(ROOT), "show", head + ":" + rel],
                               capture_output=True, check=True).stdout
    if committed != path.read_bytes():
        raise SystemExit("Commit the latest preview before deploying: " + rel)
import importlib.util
build_spec = importlib.util.spec_from_file_location('workflow_build', HERE / 'build.py')
build = importlib.util.module_from_spec(build_spec)
build_spec.loader.exec_module(build)
expected = build.render()
if expected != paths[0].read_text():
    raise SystemExit("Rebuild the standalone HTML before committing and deploying")
spec = importlib.util.spec_from_file_location('verify_live', HERE / 'verify-live.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
combined = audit.verify()
if combined['combined_commit'] != head:
    raise SystemExit('Branch changed during verification; rerun from the latest HEAD')

stage = "/tmp/workflow-studio-poc-" + head[:12]
subprocess.run(["ssh", HOST, "mkdir", "-p", stage], check=True)
subprocess.run(["rsync", "-az", "--timeout=30", *map(str, paths),
                HOST + ":" + stage + "/"], check=True, timeout=60)
remote = r'''
import pathlib, subprocess, shutil, hashlib, json, datetime, fcntl
lock=open("/tmp/payobook-studio-deploy.lock","a+")
fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
stage=pathlib.Path(STAGE)
site=pathlib.Path("/etc/nginx/sites-available/_")
snippet=pathlib.Path("/etc/nginx/snippets/workflow-studio-preview.conf")
target=pathlib.Path("/var/www/payobook-previews/workflow-studio/index.html")
backup=pathlib.Path("/odoo/backups/workflow-studio-preview-"+HEAD[:12])
backup.mkdir(parents=True, exist_ok=True, mode=0o700)
backup.chmod(0o700)
original=site.read_bytes()
prior_snippet=snippet.read_bytes() if snippet.exists() else None
prior_page=target.read_bytes() if target.exists() else None
(backup/"nginx-site-before.conf").write_bytes(original)
if prior_snippet is not None: (backup/"snippet-before.conf").write_bytes(prior_snippet)
if prior_page is not None: (backup/"preview-before.html").write_bytes(prior_page)
include="  include /etc/nginx/snippets/workflow-studio-preview.conf;\n"
text=original.decode()
if include not in text:
    marker="  location = /status {"
    if text.count(marker)!=1: raise SystemExit("Expected payobook.com status route not found; site left unchanged")
    prefix=text.split(marker,1)[0]
    if "server_name payobook.com;" not in prefix or "server_name *.payobook.com;" in prefix:
        raise SystemExit("Could not identify payobook.com server block")
    text=text.replace(marker,include+"\n"+marker,1)
target.parent.mkdir(parents=True,exist_ok=True)
snippet.parent.mkdir(parents=True,exist_ok=True)
try:
    shutil.copyfile(stage/"workflow-studio-poc.html",target)
    shutil.copyfile(stage/"nginx-location.conf",snippet)
    target.chmod(0o644);snippet.chmod(0o644)
    site.write_text(text)
    subprocess.run(["nginx","-t"],check=True)
    subprocess.run(["systemctl","reload","nginx"],check=True)
except BaseException:
    site.write_bytes(original)
    if prior_snippet is None: snippet.unlink(missing_ok=True)
    else: snippet.write_bytes(prior_snippet)
    if prior_page is None: target.unlink(missing_ok=True)
    else: target.write_bytes(prior_page)
    subprocess.run(["nginx","-t"],check=True)
    subprocess.run(["systemctl","reload","nginx"],check=True)
    raise
report={"commit":HEAD,"target":"https://payobook.com/preview/workflow-studio/","sha256":hashlib.sha256(target.read_bytes()).hexdigest(),"scope":"payobook.com standalone preview; no database or Odoo module changes", "combined_repository_audit": COMBINED}
(backup/"deployment.json").write_text(json.dumps(report,indent=2))
for p in backup.iterdir():
    if p.is_file(): p.chmod(0o600)
with pathlib.Path('/opt/deploy-notes.md').open('a') as notes:
    notes.write(datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC') + ' | Workflow Studio POC | DONE | standalone HTML preview | payobook.com preview; payobook,payobook_template,p0clone,rize verified | no restart | ' + HEAD + '; ' + str(backup) + '\n')
shutil.rmtree(stage)
print(json.dumps(report))
'''
remote = "STAGE=" + repr(stage) + "\nHEAD=" + repr(head) + "\nCOMBINED=" + repr(combined) + "\n" + remote
if subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip() != head:
    raise SystemExit('Branch changed after staging; rerun to deploy the latest combined state')
subprocess.run(["ssh", HOST, "sudo", "python3", "-"], input=remote, text=True,
               check=True, timeout=60)
print("Local SHA256:", hashlib.sha256(paths[0].read_bytes()).hexdigest())
