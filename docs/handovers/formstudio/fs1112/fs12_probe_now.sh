#!/bin/bash
# Root: read-only probe of one live database as the administrator (pre-check of the probe itself).
TS=$1; db=$2
EV=/tmp/fs12-$TS
H=$([ $db = payobook ] && echo payobook.com || echo $db.payobook.com)
cp /tmp/fs12_probe.py $EV/fs12_probe.py; chown odoo:odoo $EV/fs12_probe.py
sed -e "s#^logfile.*#logfile = $EV/probe-odoo.log#" /etc/odoo-server.conf > $EV/probe.conf; chown odoo:odoo $EV/probe.conf; chmod 600 $EV/probe.conf
sudo -u odoo env PROBE_ADMIN_ONLY=1 PROBE_HOST=$H python3 /odoo/odoo-server/odoo-bin shell -c $EV/probe.conf -d $db --no-http --max-cron-threads=0 < $EV/fs12_probe.py > $EV/probe-now-$db.out 2>&1
rm -f $EV/probe.conf
grep -E '^PROBE|Traceback|Error' $EV/probe-now-$db.out | cut -c1-300
