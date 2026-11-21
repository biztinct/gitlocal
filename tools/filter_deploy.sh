#!/bin/bash
# =====================================================================
#  filter_deploy.sh — the one deploy command for the FILTER programme.
#  Runs ON Payobook19v2 as root (installed at /odoo/ops/filter_deploy.sh).
#
#  usage:  filter_deploy.sh full  <stage_dir> <sync_modules_csv> <upgrade_modules_csv> <run_dir>
#          filter_deploy.sh looks <stage_dir> <sync_modules_csv> -                    <run_dir>
#
#  full  = Python/XML/manifest changed: backups, cron snapshot, stop,
#          rsync per module, -u per DB (stop at first failure + roll the
#          files back), restore cron states, purge assets, start, warm.
#  looks = JS/SCSS/template only: rsync per module + asset purge, no stop.
#
#  Launch it detached and poll <run_dir>/done:
#    sudo systemd-run --collect --unit=pbf-$(date -u +%H%M%S) \
#        /bin/bash /odoo/ops/filter_deploy.sh full /tmp/pbf_stage pb_x,pb_y pb_x,pb_y /tmp/pbf-run-XXXX
#  Result in <run_dir>/result (OK | FAILED_ON_<db> | BACKUP_FAILED | LOCK_FAILED | HASH_MISMATCH_<m>),
#  the log in <run_dir>/run.log, upgrade logs in <run_dir>/up_<db>.log.
#  The caller writes the START/DONE lines in /opt/deploy-notes.md.
# =====================================================================
set -u
MODE="$1"; STAGE="$2"; SYNC_CSV="$3"; UP_CSV="$4"; D="$5"
DBS="${DBS:-p0clone payobook_template rize payobook}"
ADDONS=/odoo/odoo-server/addons
mkdir -p "$D"; chmod 777 "$D"
TS="$(basename "$D")"
log() { echo "$(date -u +%H:%M:%S) $*" >> "$D/run.log"; }
finish() { echo "$1" > "$D/result"; touch "$D/done"; exit "${2:-0}"; }
tree_hash() { (cd "$1" && find . -type f ! -name "*.pyc" ! -path "*__pycache__*" ! -name .DS_Store -print0 | sort -z | xargs -0 md5sum | md5sum | cut -c1-12); }

exec 9>/tmp/payobook-studio-deploy.lock
flock -w 600 9 || finish LOCK_FAILED 1
log "start mode=$MODE sync=$SYNC_CSV upgrade=$UP_CSV"
SYNC="${SYNC_CSV//,/ }"
UP="$UP_CSV"

for m in $SYNC; do
  [ -d "$STAGE/$m" ] || { log "MISSING $STAGE/$m"; finish "MISSING_$m" 1; }
done

if [ "$MODE" = "looks" ]; then
  for m in $SYNC; do
    mkdir -p "$ADDONS/$m"; rsync -a --delete --chown=odoo:odoo "$STAGE/$m/" "$ADDONS/$m/"
    [ "$(tree_hash "$STAGE/$m")" = "$(tree_hash "$ADDONS/$m")" ] || finish "HASH_MISMATCH_$m" 1
  done
  log "files synced"
  for db in $DBS; do
    sudo -u odoo psql -d "$db" -qAt -c "delete from ir_attachment where url like '/web/assets/%';" \
      -c "update ir_config_parameter set value = '$TS' where key = 'web.assets.version';" >> "$D/run.log" 2>&1
    sudo -u odoo psql -d "$db" -qAt -c "insert into orm_signaling_assets default values;" >> "$D/run.log" 2>&1 || true
  done
  log "assets purged on $DBS"
  finish OK 0
fi

# ------------------------------------------------------------------ full
B="/odoo/backups/$TS"; mkdir -p "$B"
for db in $DBS; do
  sudo -u postgres pg_dump -Fc "$db" > "$B/$db.dump" || { log "BACKUP_FAILED $db"; finish BACKUP_FAILED 1; }
  log "backup $db $(stat -c %s "$B/$db.dump") bytes"
done
for db in $DBS; do
  sudo -u odoo psql -d "$db" -Atc "select coalesce(string_agg(id::text, ','), '') from ir_cron where active" > "$D/cron_$db.txt"
  log "crons on in $db: $(tr ',' '\n' < "$D/cron_$db.txt" | grep -c .)"
done
mkdir -p "$D/old"
for m in $SYNC; do [ -d "$ADDONS/$m" ] && cp -a "$ADDONS/$m" "$D/old/"; done

service odoo-server stop
for i in $(seq 1 30); do pgrep -f "[o]doo-server/odoo-bin" > /dev/null || break; sleep 1; done
pgrep -f "[o]doo-server/odoo-bin" | xargs -r kill -9; sleep 1
log "stopped"

for m in $SYNC; do
  mkdir -p "$ADDONS/$m"; rsync -a --delete --chown=odoo:odoo "$STAGE/$m/" "$ADDONS/$m/"
done
log "files synced"

FAIL=""
for db in $DBS; do
  # modules not installed on this DB are skipped by -u, and -i is not used:
  # a brand-new module is installed by listing it in -i via UP_CSV as "+name"
  INSTALL="$(echo "$UP" | tr ',' '\n' | grep '^+' | tr -d '+' | paste -sd, -)"
  UPGRADE="$(echo "$UP" | tr ',' '\n' | grep -v '^+' | paste -sd, -)"
  ARGS=""
  [ -n "$INSTALL" ] && ARGS="$ARGS -i $INSTALL"
  [ -n "$UPGRADE" ] && ARGS="$ARGS -u $UPGRADE"
  sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf -d "$db" $ARGS \
      --stop-after-init --no-http --max-cron-threads=0 --logfile="$D/up_$db.log"
  rc=$?
  errs=$(grep -cE " (ERROR|CRITICAL) " "$D/up_$db.log" || true)
  log "upgrade $db EXIT=$rc errors=$errs"
  if [ "$rc" -ne 0 ]; then FAIL="$db"; break; fi
done
if [ -n "$FAIL" ]; then
  for m in $SYNC; do [ -d "$D/old/$m" ] && rsync -a --delete "$D/old/$m/" "$ADDONS/$m/"; done
  log "ROLLED BACK files after failure on $FAIL (DBs already upgraded keep the new data; restore from $B if needed)"
fi

for db in $DBS; do
  ids="$(cat "$D/cron_$db.txt")"
  if [ -n "$ids" ]; then q="update ir_cron set active = (id in ($ids));"; else q="update ir_cron set active = false;"; fi
  sudo -u odoo psql -d "$db" -qAt -c "$q" \
      -c "delete from ir_attachment where url like '/web/assets/%';" \
      -c "update ir_config_parameter set value = '$TS' where key = 'web.assets.version';" >> "$D/run.log" 2>&1
  sudo -u odoo psql -d "$db" -qAt -c "insert into orm_signaling_assets default values;" >> "$D/run.log" 2>&1 || true
  log "after $db: crons on $(sudo -u odoo psql -d "$db" -Atc 'select count(*) from ir_cron where active')"
done

service odoo-server start; sleep 10
log "started: $(systemctl is-active odoo-server), procs $(pgrep -fc '[o]doo-server/odoo-bin')"
for h in payobook.com rize.payobook.com p0clone.payobook.com; do
  log "warm $h $(curl -s -o /dev/null -w '%{http_code}' --max-time 120 "https://$h/web/login")"
done
if [ -z "$FAIL" ]; then
  for m in $SYNC; do
    [ "$(tree_hash "$STAGE/$m")" = "$(tree_hash "$ADDONS/$m")" ] || finish "HASH_MISMATCH_$m" 1
  done
  for m in $SYNC; do for db in $DBS; do
    log "version $db $m $(sudo -u odoo psql -d "$db" -Atc "select state||' '||coalesce(latest_version,'') from ir_module_module where name='$m'")"
  done; done
  finish OK 0
fi
finish "FAILED_ON_$FAIL" 1
