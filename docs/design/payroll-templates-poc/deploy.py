#!/usr/bin/env python3
"""Deploy the committed, standalone preview to payobook.com, without Odoo writes."""
import hashlib
import pathlib
import subprocess
import json

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
HOST = "Payobook19v2"
head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                      capture_output=True, text=True, check=True).stdout.strip()
paths = [HERE.parent / "payroll-templates-poc.html", HERE / "nginx-location.conf"]
for path in paths:
    rel = str(path.relative_to(ROOT))
    committed = subprocess.run(["git", "-C", str(ROOT), "show", head + ":" + rel],
                               capture_output=True, check=True).stdout
    if committed != path.read_bytes():
        raise SystemExit("Commit the latest preview before deploying: " + rel)

stage = "/tmp/payroll-templates-poc-" + head[:12]
subprocess.run(["ssh", HOST, "mkdir", "-p", stage], check=True)
subprocess.run(["scp", *map(str, paths), HOST + ":" + stage + "/"], check=True)
remote = r'''
import pathlib, subprocess, shutil, hashlib, json, datetime
stage=pathlib.Path(STAGE)
site=pathlib.Path("/etc/nginx/sites-available/_")
snippet=pathlib.Path("/etc/nginx/snippets/payroll-templates-preview.conf")
target=pathlib.Path("/var/www/payobook-previews/payroll-templates/index.html")
backup=pathlib.Path("/odoo/backups/payroll-templates-preview-"+HEAD[:12])
backup.mkdir(parents=True, exist_ok=True, mode=0o700)
backup.chmod(0o700)
original=site.read_bytes()
prior_snippet=snippet.read_bytes() if snippet.exists() else None
prior_page=target.read_bytes() if target.exists() else None
(backup/"nginx-site-before.conf").write_bytes(original)
if prior_snippet is not None: (backup/"snippet-before.conf").write_bytes(prior_snippet)
if prior_page is not None: (backup/"preview-before.html").write_bytes(prior_page)
include="  include /etc/nginx/snippets/payroll-templates-preview.conf;\n"
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
    shutil.copyfile(stage/"payroll-templates-poc.html",target)
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
report={"commit":HEAD,"target":"https://payobook.com/preview/payroll-templates/","sha256":hashlib.sha256(target.read_bytes()).hexdigest(),"scope":"payobook.com standalone preview; no database or Odoo module changes"}
(backup/"deployment.json").write_text(json.dumps(report,indent=2))
for p in backup.iterdir():
    if p.is_file(): p.chmod(0o600)
shutil.rmtree(stage)
print(json.dumps(report))
'''
remote = "STAGE=" + repr(stage) + "\nHEAD=" + repr(head) + "\n" + remote
subprocess.run(["ssh", HOST, "sudo", "python3", "-"], input=remote, text=True,
               check=True, timeout=60)
print("Local SHA256:", hashlib.sha256(paths[0].read_bytes()).hexdigest())
