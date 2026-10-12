"""Run as root on Biztinct after configuration backups, before Odoo restart.

Only changes proxy routing/header correctness, Odoo proxy mode and the
production database routing. Never
prints configuration contents or credentials. No database access settings
are changed. nginx syntax is checked before reloading is allowed.
"""
import re
import subprocess
from pathlib import Path


def main():
    nginx = Path('/etc/nginx/sites-enabled/odoo-443')
    odoo = Path('/etc/odoo-server.conf')
    original_nginx = nginx.read_text()
    original_odoo = odoo.read_text()
    updated_nginx = original_nginx.replace(
        'proxy_pass http://54.206.115.180:', 'proxy_pass http://127.0.0.1:')
    updated_nginx = updated_nginx.replace(
        'proxy_set_header X-Forward-For ', 'proxy_set_header X-Forwarded-For ')
    updated_odoo = original_odoo
    # The server serves one production DB. Restored QA databases must never
    # alter public routing or expose a database selector on the website.
    for key, value in [('proxy_mode', 'True'), ('db_name', 'biztinctprod'),
                       ('dbfilter', '^biztinctprod$')]:
        if re.search(r'^\s*%s\s*=' % key, updated_odoo, flags=re.M):
            updated_odoo = re.sub(r'^\s*%s\s*=.*$' % key, '%s = %s' % (key, value),
                                  updated_odoo, flags=re.M)
        else:
            updated_odoo = updated_odoo.rstrip() + '\n%s = %s\n' % (key, value)
    try:
        nginx.write_text(updated_nginx)
        odoo.write_text(updated_odoo)
        subprocess.run(['nginx', '-t'], check=True)
    except Exception:
        nginx.write_text(original_nginx)
        odoo.write_text(original_odoo)
        raise
    print('Proxy configuration checked; nginx reload required after Odoo restart.')


if __name__ == '__main__':
    main()
