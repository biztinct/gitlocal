#!/bin/bash
# =====================================================================
#  pbf_preview.sh — the shared PREVIEW server for the FILTER programme.
#  Runs ON Payobook19v2 as root (installed at /odoo/ops/pbf_preview.sh).
#
#  One throwaway database (`pbf_preview`, a copy of payobook, jobs and mail
#  switched off) served by a second Odoo on 127.0.0.1:8170 whose addons
#  path starts with /tmp/pbf_preview/addons — so whatever a builder syncs
#  there wins over the live copy. Reach it from the Mac through a tunnel:
#      ssh -f -N -L 8170:127.0.0.1:8170 Payobook19v2   →   http://localhost:8170
#
#  Builders take turns: every command below waits for the preview lock.
#    pbf_preview.sh hold  <who>               take the lock for a test pass (writes /tmp/pbf_preview/holder)
#    pbf_preview.sh release <who>             give it back
#    pbf_preview.sh sync <src_dir> <mods_csv> copy modules from a staging dir into the preview addons
#    pbf_preview.sh upgrade <mods_csv>        stop, -u (or +name to install) on pbf_preview, start
#    pbf_preview.sh restart                   stop + start (JS/SCSS/XML only; purges the bundles)
#    pbf_preview.sh status                    pid, port, holder, versions of the synced modules
#    pbf_preview.sh reset                     drop and re-copy the database from payobook (coordinator only)
#  Log: /tmp/pbf_preview/server.log. Login: /tmp/pbf_preview/.login (user + password of the admin on the copy).
# =====================================================================
set -u
CMD="${1:-status}"
P=/tmp/pbf_preview
DB=pbf_preview
PORT=8170
mkdir -p "$P/addons"; chmod 777 "$P" "$P/addons" 2>/dev/null
LOCK="$P/lock"; HOLDER="$P/holder"
ODOO="sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf --addons-path=$P/addons,/odoo/odoo-server/addons"
SERVE_ARGS="-d $DB --db-filter=^$DB\$ --http-port=$PORT --gevent-port=8172 --workers=0 --max-cron-threads=0 --no-database-list --logfile=$P/server.log"

pid() { pgrep -f "http-port=$PORT" | head -1; }
stop() { local p; p="$(pid)"; if [ -n "$p" ]; then kill "$p"; for i in $(seq 1 20); do pgrep -f "http-port=$PORT" > /dev/null || break; sleep 1; done; pgrep -f "http-port=$PORT" | xargs -r kill -9; fi; }
start() {
  sudo -u odoo psql -d "$DB" -qAt -c "delete from ir_attachment where url like '/web/assets/%';" 2>/dev/null || true
  cd /tmp && nohup $ODOO $SERVE_ARGS > /dev/null 2>&1 &
  for i in $(seq 1 60); do curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$PORT/web/login" && break; sleep 2; done
  echo "preview http $(curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:$PORT/web/login) pid $(pid)"
}

case "$CMD" in
  hold)
    who="${2:-unknown}"
    exec 9>"$LOCK"
    if ! flock -n 9; then echo "waiting for $(cat "$HOLDER" 2>/dev/null || echo someone) to release the preview…"; flock -w 7200 9 || { echo LOCK_TIMEOUT; exit 1; }; fi
    echo "$who $(date -u +%H:%M)" > "$HOLDER"
    # keep the lock alive in a background holder process the releaser can kill
    nohup bash -c "exec 9>'$LOCK'; flock 9; echo \$\$ > '$P/lockpid'; while [ -f '$HOLDER' ]; do sleep 5; done" > /dev/null 2>&1 &
    sleep 1; echo "HELD by $who"
    ;;
  release)
    rm -f "$HOLDER"; sleep 6; echo RELEASED
    ;;
  sync)
    src="$2"; for m in ${3//,/ }; do
      [ -d "$src/$m" ] || { echo "MISSING $src/$m"; exit 1; }
      rsync -a --delete --chown=odoo:odoo "$src/$m/" "$P/addons/$m/"; echo "synced $m"
    done
    ;;
  upgrade)
    mods="$2"; INSTALL="$(echo "$mods" | tr ',' '\n' | grep '^+' | tr -d '+' | paste -sd, -)"; UPGRADE="$(echo "$mods" | tr ',' '\n' | grep -v '^+' | paste -sd, -)"
    ARGS=""; [ -n "$INSTALL" ] && ARGS="$ARGS -i $INSTALL"; [ -n "$UPGRADE" ] && ARGS="$ARGS -u $UPGRADE"
    stop
    cd /tmp && $ODOO -d "$DB" $ARGS --stop-after-init --no-http --max-cron-threads=0 --logfile="$P/upgrade.log"
    rc=$?; echo "upgrade EXIT=$rc errors=$(grep -cE ' (ERROR|CRITICAL) ' "$P/upgrade.log" || true)"
    sudo -u odoo psql -d "$DB" -qAt -c "update ir_cron set active=false; update ir_mail_server set active=false;"
    start
    ;;
  restart) stop; start ;;
  stop) stop; echo stopped ;;
  start) start ;;
  status)
    echo "pid=$(pid) port=$PORT holder=$(cat "$HOLDER" 2>/dev/null || echo none) http=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:$PORT/web/login)"
    ls "$P/addons" 2>/dev/null | tr '\n' ' '; echo
    ;;
  reset)
    stop
    sudo -u postgres dropdb --force --if-exists "$DB"
    sudo -u postgres createdb -O odoo "$DB"
    sudo -u postgres pg_dump -Fc payobook > "$P/payobook.dump"
    sudo -u postgres pg_restore --no-owner --role=odoo -d "$DB" "$P/payobook.dump"
    sudo -u odoo psql -d "$DB" -qAt -c "update ir_cron set active=false; update ir_mail_server set active=false; update ir_config_parameter set value='http://127.0.0.1:$PORT' where key='web.base.url';"
    rm -rf "/odoo/.local/share/Odoo/filestore/$DB"; cp -a /odoo/.local/share/Odoo/filestore/payobook "/odoo/.local/share/Odoo/filestore/$DB" 2>/dev/null || true
    chown -R odoo:odoo "/odoo/.local/share/Odoo/filestore/$DB" 2>/dev/null || true
    echo "database reset from payobook"
    ;;
  *) echo "usage: hold|release|sync|upgrade|restart|start|stop|status|reset"; exit 1 ;;
esac
