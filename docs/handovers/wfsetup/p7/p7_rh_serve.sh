#!/bin/bash
# WFSETUP P7: serve the REHEARSAL copy alone on 127.0.0.1:8277 (reach it through an ssh tunnel), live code,
# no jobs, its own log. Port + unit differ from p5b's 8299 / wfs-rh-serve (a peer agent may use those).
# Clone of ../p5b/wfs_rh_serve.sh. Root: bash p7_rh_serve.sh <TS> start|stop [src]
TS=$1; ACT=$2; SRC=${3:-rize}
EV=/tmp/wfsetup-p7-$TS
COPY=wfs_rh7_$SRC
if [ "$ACT" = stop ]; then systemctl stop wfs-rh7-serve; systemctl reset-failed wfs-rh7-serve 2>/dev/null; echo "stopped: $(systemctl is-active wfs-rh7-serve)"; exit 0; fi
sed -e "s#^logfile.*#logfile = $EV/rh-serve.log#" -e "s#^dbfilter.*#dbfilter = #" -e "s#^list_db.*#list_db = True#" \
    -e "s#^http_port.*#http_port = 8277#" -e "s#^proxy_mode.*#proxy_mode = False#" $EV/rh-$SRC.conf > $EV/rh-serve.conf
chown odoo:odoo $EV/rh-serve.conf; chmod 600 $EV/rh-serve.conf
systemd-run --unit=wfs-rh7-serve --uid=odoo --gid=odoo -E HOME=/odoo --working-directory=/odoo \
  /usr/bin/python3 /odoo/odoo-server/odoo-bin -c $EV/rh-serve.conf -d $COPY --http-interface=127.0.0.1 \
  --gevent-port=8276 --max-cron-threads=0 --workers=0
for i in $(seq 1 90); do ss -ltn | grep -q '127.0.0.1:8277 ' && break; sleep 1; done
echo "port 8277 $(ss -ltn | grep -q '127.0.0.1:8277 ' && echo listening || echo NOT-LISTENING); login page $(curl -s -o /dev/null -m 60 -w '%{http_code}' http://127.0.0.1:8277/web/login)"
