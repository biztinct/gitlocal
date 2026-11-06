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
module_state=$(sudo -u postgres psql -d biztinctprod -Atc \
    "SELECT state FROM ir_module_module WHERE name = 'biztinct_website'")
module_args=(-i biztinct_website)
if [[ "$module_state" == "installed" ]]; then
    # -i would replay noupdate data and reset the user's SMTP configuration.
    module_args=(-u biztinct_website)
fi
systemctl stop odoo-server
trap 'systemctl start odoo-server' EXIT
sudo -u odoo python3 /odoo/odoo-server/odoo-bin \
    -c /etc/odoo-server.conf -d biztinctprod "${module_args[@]}" \
    --no-http --stop-after-init --without-demo=all \
    --logfile="$backup/production-install.log"
systemctl start odoo-server
systemctl reload nginx
systemctl is-active odoo-server
systemctl is-active nginx
echo 'Biztinct production publish completed.'
