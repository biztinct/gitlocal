#!/bin/bash
# INBOX-BULK-BANK: re-take the read-only "pages before" probe on the five live databases with the
# current probe (session block left out of the page hash). Root: bash ibb_pages_before.sh <TS>
TS=$1
EV=/tmp/ibb-$TS
cp /tmp/ibb_probe.py $EV/ && chown odoo:odoo $EV/ibb_probe.py
sed -e "s#^logfile.*#logfile = $EV/probe-odoo.log#" /etc/odoo-server.conf > $EV/probe.conf; chown odoo:odoo $EV/probe.conf; chmod 600 $EV/probe.conf
for db in payobook payobook_template p0clone rize sudima; do
  H=$([ $db = payobook ] && echo payobook.com || echo $db.payobook.com)
  sudo -u odoo env IBB_MODE=pages PROBE_HOST=$H python3 /odoo/odoo-server/odoo-bin shell -c $EV/probe.conf -d $db --no-http --max-cron-threads=0 < $EV/ibb_probe.py > $EV/probe-pages-before-$db.out 2>&1
  echo "$(date -u +%T) $db pages before (again): $(grep -E '^PROBE|Traceback' $EV/probe-pages-before-$db.out | sed 's/^PROBE //' | tr '\n' ';' | cut -c1-900)" >> $EV/steps.log
done
rm -f $EV/probe.conf
touch $EV/pages-before.done
