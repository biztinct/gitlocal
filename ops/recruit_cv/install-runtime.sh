#!/bin/bash
# Run as root after staging services/recruit_cv at /odoo/services/recruit_cv.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends acl python3-venv libglib2.0-0 libgl1 libgomp1 tesseract-ocr tesseract-ocr-eng tesseract-ocr-vie tesseract-ocr-ind fonts-dejavu-core
getent passwd recruit-cv >/dev/null || useradd --system --home-dir /var/lib/recruit-cv --create-home --shell /usr/sbin/nologin recruit-cv
# Traverse the protected Odoo parent without joining its privileged group.
setfacl -m u:recruit-cv:--x /odoo
install -d -o recruit-cv -g recruit-cv -m 750 /var/lib/recruit-cv/models
install -d -m 755 /odoo/venvs /etc/payobook
python3 -m venv /odoo/venvs/recruit-cv
/odoo/venvs/recruit-cv/bin/pip install --no-cache-dir torch==2.13.0 torchvision==0.28.0 --index-url https://download.pytorch.org/whl/cpu
requirements=/odoo/services/recruit_cv/requirements.txt
if [ -f /odoo/services/recruit_cv/requirements-linux.lock ]; then
    requirements=/odoo/services/recruit_cv/requirements-linux.lock
fi
/odoo/venvs/recruit-cv/bin/pip install --no-cache-dir -r "$requirements"
/odoo/venvs/recruit-cv/bin/pip check
/odoo/venvs/recruit-cv/bin/pip freeze > /odoo/services/recruit_cv/installed-linux.lock
# Service key is generated only on first install and never printed or committed.
python3 - <<'PY'
import os,secrets
from pathlib import Path
p=Path('/etc/payobook/recruit-cv.env')
if not p.exists():
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:
        f.write('RECRUIT_CV_KEY='+secrets.token_urlsafe(48)+'\n')
        f.write('RECRUIT_CV_OCR=tesseract\nRECRUIT_CV_THREADS=2\n')
PY
