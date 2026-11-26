#!/bin/bash
# PSCHEME P3 D: run ps3_fillcheck.py on one live database (read-only). Root: bash ps3_runcheck.sh <db> <label> [before_label]
DB=$1; L=$2; B=$3
EV=/tmp/pscheme-p3-20261126T2005Z
cp /tmp/ps3_fillcheck.py $EV/ && chown odoo:odoo $EV/ps3_fillcheck.py
sed -e "s#^logfile.*#logfile = $EV/check-odoo.log#" /etc/odoo-server.conf > $EV/check.conf; chown odoo:odoo $EV/check.conf; chmod 600 $EV/check.conf
EXTRA=""; [ -n "$B" ] && EXTRA="PS3_BEFORE=$EV/fillcheck-$DB-$B.json"
sudo -u odoo env PS3_OUT=$EV/fillcheck-$DB-$L.json $EXTRA python3 /odoo/odoo-server/odoo-bin shell -c $EV/check.conf -d $DB --no-http --max-cron-threads=0 < $EV/ps3_fillcheck.py > $EV/fillcheck-$DB-$L.out 2>&1
rm -f $EV/check.conf
grep -E '^PROBE|Error|Traceback' $EV/fillcheck-$DB-$L.out | cut -c1-600
