"""Install the private location in the existing Payobook TLS virtual host."""
import pathlib
import shutil
import subprocess

site = pathlib.Path('/etc/nginx/sites-enabled/_').resolve()
fragment = pathlib.Path('/etc/nginx/snippets/recruit-cv.conf')
source = pathlib.Path('/tmp/recruit-cv-activation-20261024/nginx-location.conf')
backup = pathlib.Path('/odoo/backups/recruit-cv-activation-20261024-config')
backup.mkdir(mode=0o700, parents=True, exist_ok=True)
original = site.read_text()
if not (backup/'payobook-nginx-before.conf').exists():
    shutil.copy2(site, backup/'payobook-nginx-before.conf')
if fragment.exists() and not (backup/'recruit-cv-before.conf').exists():
    shutil.copy2(fragment, backup/'recruit-cv-before.conf')
include = '  include /etc/nginx/snippets/recruit-cv.conf;'
assert 'server_name payobook.com;' in original and 'listen 443 ssl' in original
shutil.copy2(source, fragment)
if include not in original:
    site.write_text(original.replace('  server_name payobook.com;', '  server_name payobook.com;\n'+include, 1))
try:
    subprocess.run(['nginx', '-t'], check=True)
except Exception:
    site.write_text(original)
    raise
subprocess.run(['systemctl','reload','nginx'],check=True)
print('Private parser route installed; existing TLS and other tenants preserved.')
