#!/bin/bash
# FS-15 after go-live: employee pages (My Payobook, My Profile, My details, My Leave) for up to 3 newest
# employee logins per site, opened server side (read-only GETs). Root: bash fs15_after.sh <TS>
TS=$1
EV=/tmp/fs15-$TS
sed -e "s#^logfile.*#logfile = $EV/after-odoo.log#" /etc/odoo-server.conf > $EV/after.conf; chown odoo:odoo $EV/after.conf; chmod 600 $EV/after.conf
for db in payobook payobook_template p0clone rize sudima; do
  H=$([ $db = payobook ] && echo payobook.com || echo $db.payobook.com)
  sudo -u odoo env PROBE_HOST=$H python3 /odoo/odoo-server/odoo-bin shell -c $EV/after.conf -d $db --no-http --max-cron-threads=0 < $EV/fs15_probe.py > $EV/after-$db.out 2>&1
  echo "$db: $(grep -E '^PROBE page emp' $EV/after-$db.out | sed -E 's/[0-9a-f]{10}//g' | tr '\n' ';' | cut -c1-400) failed=$(grep -E '^PROBE page emp' $EV/after-$db.out | grep -oE ' [0-9]{3} ' | grep -vc ' 200 ') traceback=$(grep -c Traceback $EV/after-$db.out)"
done
rm -f $EV/after.conf
