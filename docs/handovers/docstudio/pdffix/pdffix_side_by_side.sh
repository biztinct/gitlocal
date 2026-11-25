#!/bin/bash
# DOCSTUDIO PDFFIX step 1: the same documents through the application with the OLD engine
# (/usr/bin/wkhtmltopdf, Ubuntu build) and the NEW one (unpacked patched-Qt build, never
# installed), one server shell per database per engine. Only PATH of that one shell process
# differs. Nothing is stored (the probe rolls back). Run as root on the server:
#   EV=/odoo/backups/docstudio-pdffix-<stamp> NEWBIN=/tmp/pdffix-20261124/x/usr/local/bin \
#     bash pdffix_side_by_side.sh payobook rize sudima
set -u
EV=${EV:?}; NEWBIN=${NEWBIN:?}
mkdir -p $EV && chown odoo:odoo $EV && chmod 750 $EV
cp /tmp/pdffix_probe.py $EV/ && chown odoo:odoo $EV/pdffix_probe.py
sed -e "s#^logfile.*#logfile = $EV/probe-odoo.log#" /etc/odoo-server.conf > $EV/probe.conf
chown odoo:odoo $EV/probe.conf; chmod 600 $EV/probe.conf
BASEPATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/bin      # the service's own PATH (init script)
for db in "$@"; do
  for tag in old new; do
    P=$BASEPATH; [ $tag = new ] && P=$NEWBIN:$BASEPATH
    mkdir -p $EV/$db-$tag && chown odoo:odoo $EV/$db-$tag
    # the engine fetches the page styles from the running site: a probe while the service is down
    # makes unstyled PDFs silently (hit 2026-11-24: another deployer restarted mid-run)
    PID0=$(pgrep -f 'odoo-bin -c /etc/odoo-server.conf$' | head -1)
    UP0=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 https://payobook.com/web/login)
    sudo -u odoo env PATH=$P OUT=$EV/$db-$tag DB=$db python3 /odoo/odoo-server/odoo-bin shell \
      -c $EV/probe.conf -d $db --no-http --max-cron-threads=0 < $EV/pdffix_probe.py > $EV/$db-$tag.out 2>&1
    PID1=$(pgrep -f 'odoo-bin -c /etc/odoo-server.conf$' | head -1)
    UP1=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 https://payobook.com/web/login)
    echo "$(date -u +%T) $db $tag: site $UP0/$UP1 service pid $PID0/$PID1 $( [ "$UP0$UP1" = 200200 ] && [ "$PID0" = "$PID1" ] && echo VALID || echo 'INVALID-SITE-DOWN-OR-RESTARTED') $(grep -E '^PROBE' $EV/$db-$tag.out | sed 's/^PROBE //' | tr '\n' ';' | cut -c1-900)"
  done
done
rm -f $EV/probe.conf
echo SIDE-BY-SIDE DONE
