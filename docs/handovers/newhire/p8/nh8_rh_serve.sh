#!/bin/bash
# NEWHIRE P8: serve ONE rehearsal copy alone on 127.0.0.1:8299 (reach it through an ssh tunnel), with
# the staged trees first, no jobs, its own log. The copy stays a template database, so the conf lists
# exactly that database (no filter). Clone of ../p5b/nh_rh_serve.sh.
# Root: bash nh8_rh_serve.sh <TS> start|stop <src>
TS=$1; ACT=$2; SRC=$3
EV=/tmp/newhire-p8-$TS
COPY=nh8_rh_$SRC
if [ "$ACT" = stop ]; then systemctl stop nh8-rh-serve; systemctl reset-failed nh8-rh-serve 2>/dev/null; echo "stopped: $(systemctl is-active nh8-rh-serve)"; exit 0; fi
ss -ltn | grep -q '127.0.0.1:8299 ' && { echo "port 8299 already in use - not starting"; exit 1; }
sed -e "s#^logfile.*#logfile = $EV/rh-serve.log#" -e "s#^dbfilter.*#dbfilter = #" -e "s#^list_db.*#list_db = True#" \
    -e "s#^http_port.*#http_port = 8299#" -e "s#^proxy_mode.*#proxy_mode = False#" $EV/rh-$SRC.conf > $EV/rh-serve.conf
chown odoo:odoo $EV/rh-serve.conf; chmod 600 $EV/rh-serve.conf
systemd-run --unit=nh8-rh-serve --uid=odoo --gid=odoo -E HOME=/odoo --working-directory=/odoo \
  /usr/bin/python3 /odoo/odoo-server/odoo-bin -c $EV/rh-serve.conf -d $COPY --http-interface=127.0.0.1 \
  --gevent-port=8298 --max-cron-threads=0 --workers=0
for i in $(seq 1 90); do ss -ltn | grep -q '127.0.0.1:8299 ' && break; sleep 1; done
echo "port 8299 $(ss -ltn | grep -q '127.0.0.1:8299 ' && echo listening || echo NOT-LISTENING); login page $(curl -s -o /dev/null -m 60 -w '%{http_code}' http://127.0.0.1:8299/web/login)"
