#!/usr/bin/env bash
# Execute on Biztinct with sudo after staging and QA. No credentials in this file.
set -euo pipefail
stage=/tmp/biztinct-web-stage-20261012/biztinct_website
target=/odoo/odoo-server/addons/biztinct_website
backup=/odoo/backups/biztinct-web-20261012
test -f "$stage/views/templates.xml"
test -s "$backup/biztinctprod-before.dump"
rsync -a --delete --chown=odoo:odoo "$stage/" "$target/"
chmod -R u=rwX,go=rX "$target"
python3 "$target/deploy/configure_proxy.py"
systemctl stop odoo-server
trap 'systemctl start odoo-server' EXIT
sudo -u odoo python3 /odoo/odoo-server/odoo-bin \
    -c /etc/odoo-server.conf -d biztinctprod -i biztinct_website \
    --no-http --stop-after-init --without-demo=all \
    --logfile="$backup/production-install.log"
systemctl start odoo-server
systemctl reload nginx
systemctl is-active odoo-server
systemctl is-active nginx
echo 'Biztinct production publish completed.'
