#!/bin/bash
# =====================================================================
#  pb_release.sh — the ONE release script. Runs ON the server as root
#  (installed at /odoo/ops/pb_release.sh by tools/release.sh).
#
#  usage: pb_release.sh <tier> <stage_dir> <sync_modules_csv> <upgrade_csv|-> <run_dir>
#    tier  looks   JS/SCSS/templates only: copy + asset refresh, NO stop, NO upgrade
#          normal  Python/views/strings, no stored-data change: stop, upgrade every DB, start
#          risky   anything that rewrites stored data / new module / pay / access
#    upgrade_csv: modules for -u; prefix a name with + to -i (install) instead.
#
#  env: WHO (note author), COMMIT (git hash), DBS (default: all five)
#       BACKUP=nightly (default) | fresh | none
#         nightly: each DB must have a nightly backup < 30h old with an OK file,
#                  else THAT DB gets a fresh dump (never a silent no-backup).
#         fresh:   fresh pg_dump of every DB   (truly dangerous change)
#       FRESH_DBS="db1 db2": fresh dump only for these DBs, nightly for the rest.
#
#  Steps: lock -> notes START -> backup check -> cron snapshot -> stop ->
#  copy (per module, --delete scoped) -> upgrade each DB (stop at first failure,
#  roll files back) -> restore cron states -> asset refresh -> start -> warm ->
#  hash + version check -> notes DONE/FAILED, with per-step seconds.
#  Result: <run_dir>/result (OK | FAILED_ON_<db> | BACKUP_FAILED | LOCK_FAILED |
#  HASH_MISMATCH_<m> | MISSING_<m> | NOTES_BUSY), log: <run_dir>/run.log
# =====================================================================
set -uo pipefail
TIER="$1"; STAGE="$2"; SYNC_CSV="$3"; UP_CSV="$4"; D="$5"
WHO="${WHO:-Claude}"; COMMIT="${COMMIT:-unknown}"
DBS="${DBS:-payobook payobook_template p0clone rize sudima}"
BACKUP="${BACKUP:-nightly}"; FRESH_DBS="${FRESH_DBS:-}"
ADDONS=/odoo/odoo-server/addons
NOTES=/opt/deploy-notes.md
NIGHTLY=/odoo/nightly-backups
case " $DBS " in *" abm "*) echo "Refused retired database" >&2; exit 2;; esac
for db in $DBS; do [[ "$db" =~ ^[a-z][a-z0-9_]*$ ]] || exit 2; done
mkdir -m 755 "$D" || exit 2
TS="$(basename "$D")"
T0=$(date +%s); TL=$T0
log()  { echo "$(date -u +%H:%M:%S) $*" >> "$D/run.log"; }
lap()  { local n=$(date +%s); log "STEP $1 took $((n-TL))s"; TL=$n; }
note() { echo "$(date -u '+%Y-%m-%d %H:%M UTC') | $WHO | $1 | $SYNC_CSV | ${DBS// /,} | $2 | $3" >> "$NOTES"; }
finish() {
  echo "$1" > "$D/result"
  local total=$(( $(date +%s) - T0 ))
  if [ "$1" = OK ]; then note DONE "${DOWN:-0}s down, ${total}s total" "tier=$TIER commit=$COMMIT backup=$BACKUP; steps in $D/run.log"
  else note FAILED "${DOWN:-0}s down" "$1 tier=$TIER commit=$COMMIT; see $D/run.log"; fi
  touch "$D/done"; exit "${2:-0}"
}
tree_hash() { (cd "$1" && find . -type f ! -name "*.pyc" ! -path "*__pycache__*" ! -name .DS_Store -print0 | sort -z | xargs -0 md5sum | md5sum | cut -c1-12); }
host_of() { [ "$1" = payobook ] && echo payobook.com || echo "$1.payobook.com"; }

exec 9>/tmp/payobook-studio-deploy.lock
flock -w 600 9 || finish LOCK_FAILED 1
notes_clear() {
  tail -40 "$NOTES" | awk -v own="${1:-}" -F'|' '{
    who=$2; action=$3; gsub(/^[[:space:]]+|[[:space:]]+$/, "", action);
    if (action=="HOLD") held=1;
    if (action=="START") open[who]++;
    if (action=="DONE" && open[who]>0 && --open[who]==0) delete open[who];
    } END { for (who in open) if (open[who]>0 && (who!=own || open[who]>1)) busy=1; exit (held || busy) }'
}
if ! notes_clear; then echo NOTES_BUSY > "$D/result"; touch "$D/done"; exit 1; fi
log "start tier=$TIER sync=$SYNC_CSV upgrade=$UP_CSV dbs=$DBS backup=$BACKUP"
note START "${DOWN_EXPECT:-tier $TIER}" "tier=$TIER commit=$COMMIT backup=$BACKUP upgrade=$UP_CSV"
SYNC="${SYNC_CSV//,/ }"
for m in $SYNC; do [ -d "$STAGE/$m" ] || { log "MISSING $STAGE/$m"; finish "MISSING_$m" 1; }; done

sync_files() {
  for m in $SYNC; do
    mkdir -p "$ADDONS/$m" && rsync -a --delete --chown=odoo:odoo --chmod=Du+rwx,Dgo+rx,Fu+rw,Fgo+r "$STAGE/$m/" "$ADDONS/$m/" || return 1
  done
}
refresh_assets() {
  for db in $DBS; do
    sudo -u odoo psql -d "$db" -qAt -c "delete from ir_attachment where url like '/web/assets/%';" \
      -c "update ir_config_parameter set value = '$TS' where key = 'web.assets.version';" >> "$D/run.log" 2>&1
    sudo -u odoo psql -d "$db" -qAt -c "insert into orm_signaling_assets default values;" >> "$D/run.log" 2>&1 || true
  done
}
verify() {
  for m in $SYNC; do
    [ "$(tree_hash "$STAGE/$m")" = "$(tree_hash "$ADDONS/$m")" ] || finish "HASH_MISMATCH_$m" 1
  done
  if [ "$TIER" = looks ] || [ "$UP_CSV" = - ]; then return 0; fi
  for m in $(echo "$UP_CSV" | tr ',' ' ' | tr -d '+'); do for db in $DBS; do
    expected=$(python3 -c 'import ast,sys; print(ast.literal_eval(open(sys.argv[1]).read())["version"])' "$ADDONS/$m/__manifest__.py") || finish "VERSION_UNREADABLE_$m" 1
    actual=$(sudo -u odoo psql -v ON_ERROR_STOP=1 -d "$db" -Atc "select state||' '||coalesce(latest_version,'') from ir_module_module where name='$m'") || finish "VERSION_FAILED_$db" 1
    log "version $db $m $actual"
    if [[ ",$UP_CSV," != *",+$m,"* ]] && ! grep -Fxq "$m" "$D/installed_$db.txt"; then
      continue
    fi
    [ "$actual" = "installed $expected" ] || finish "VERSION_MISMATCH_${db}_$m" 1
  done; done
}

# ------------------------------------------------------------ looks: no stop
if [ "$TIER" = looks ]; then
  sync_files || finish COPY_FAILED 1; lap copy
  refresh_assets; lap assets
  verify; lap verify
  DOWN=0; finish OK 0
fi

# ------------------------------------------------------------ backups
B="/odoo/backups/$TS"; install -d -m 700 "$B" || finish BACKUP_FAILED 1
for db in $DBS; do
  fresh=0
  [ "$BACKUP" = fresh ] && fresh=1
  for f in $FRESH_DBS; do [ "$f" = "$db" ] && fresh=1; done
  if [ "$BACKUP" = none ]; then log "backup $db: SKIPPED (BACKUP=none)"; continue; fi
  if [ "$fresh" = 0 ]; then
    latest="$(ls -1 "$NIGHTLY/$db" 2>/dev/null | sort | tail -1)"
    ok="$NIGHTLY/$db/$latest/OK"
    if [ -n "$latest" ] && [ -f "$ok" ] && [ $(( $(date +%s) - $(stat -c %Y "$ok") )) -lt 108000 ]; then
      log "backup $db: using nightly $latest (OK, $(( ($(date +%s) - $(stat -c %Y "$ok"))/3600 ))h old)"
      continue
    fi
    log "backup $db: no fresh nightly -> taking a fresh dump"
  fi
  sudo -u postgres pg_dump -Fc "$db" > "$B/$db.dump" || { log "BACKUP_FAILED $db"; finish BACKUP_FAILED 1; }
  log "backup $db: fresh dump $(stat -c %s "$B/$db.dump") bytes"
done
lap backup

for db in $DBS; do
  sudo -u odoo psql -v ON_ERROR_STOP=1 -d "$db" -At -F '|' -c "select id,active from ir_cron order by id" > "$D/cron_$db.txt" || finish "CRON_SNAPSHOT_FAILED_$db" 1
  sudo -u odoo psql -v ON_ERROR_STOP=1 -d "$db" -Atc "select name from ir_module_module where state='installed'" > "$D/installed_$db.txt" || finish "MODULE_SNAPSHOT_FAILED_$db" 1
  install -o odoo -g odoo -m 640 /dev/null "$D/up_$db.log" || finish LOG_SETUP_FAILED 1
done
mkdir -p "$D/old"
for m in $SYNC; do [ -d "$ADDONS/$m" ] && cp -a "$ADDONS/$m" "$D/old/"; done
lap snapshot

# ------------------------------------------------------------ stop / copy / upgrade
if [[ ",$UP_CSV," == *",+pb_joining,"* ]]; then
  python3 "$STAGE/.release/joining/nginx.py" "$D/nginx-before" $DBS >> "$D/run.log" 2>&1 || finish NGINX_REDACTION_FAILED 1
  lap "joining redaction"
  while :; do
    notes_clear " $WHO " || finish NOTES_BUSY 1
    idle=1
    for db in payobook rize sudima; do
      [[ " $DBS " == *" $db "* ]] || continue
      present=$(sudo -u odoo psql -v ON_ERROR_STOP=1 -d "$db" -Atc "select count(*) from mail_presence where user_id is not null and last_presence > (now() at time zone 'UTC') - interval '15 minutes'") || finish "PRESENCE_FAILED_$db" 1
      [ "$present" = 0 ] || idle=0
    done
    [ "$idle" = 1 ] && break
    log "Waiting for fifteen minutes of inactivity"; sleep 30
  done
fi
TD=$(date +%s)
service odoo-server stop
for i in $(seq 1 30); do pgrep -f "[o]doo-server/odoo-bin" > /dev/null || break; sleep 1; done
pgrep -f "[o]doo-server/odoo-bin" | xargs -r kill -9; sleep 1
lap stop
sync_files || { service odoo-server start; finish COPY_FAILED 1; }; lap copy

INSTALL="$(echo "$UP_CSV" | tr ',' '\n' | grep '^+' | tr -d '+' | paste -sd, -)"
UPGRADE="$(echo "$UP_CSV" | tr ',' '\n' | grep -v '^+' | grep -v '^-$' | paste -sd, -)"
ARGS=""; [ -n "$INSTALL" ] && ARGS="$ARGS -i $INSTALL"; [ -n "$UPGRADE" ] && ARGS="$ARGS -u $UPGRADE"
FAIL=""
for db in $DBS; do
  sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf -d "$db" $ARGS \
      --stop-after-init --no-http --max-cron-threads=0 --logfile="$D/up_$db.log"
  rc=$?
  log "upgrade $db EXIT=$rc errors=$(grep -cE ' (ERROR|CRITICAL) ' "$D/up_$db.log" || true)"
  lap "upgrade $db"
  [ "$rc" -ne 0 ] && { FAIL="$db"; break; }
done
if [ -n "$FAIL" ]; then
  for m in $SYNC; do [ -d "$D/old/$m" ] && rsync -a --delete "$D/old/$m/" "$ADDONS/$m/"; done
  log "ROLLED BACK files after failure on $FAIL (DBs already upgraded keep new data; backups: nightly or $B)"
fi

# ------------------------------------------------------------ cron restore / assets / start / warm
for db in $DBS; do
  {
    echo 'BEGIN; CREATE TEMP TABLE pb_release_previous_cron(id integer PRIMARY KEY, active boolean);'
    echo "COPY pb_release_previous_cron FROM STDIN WITH (DELIMITER '|');"
    cat "$D/cron_$db.txt"
    echo '\.'
    cat "$STAGE/.release/joining/restore-cron.sql"
    echo 'COMMIT;'
  } | sudo -u odoo psql -v ON_ERROR_STOP=1 -d "$db" -qAt >> "$D/run.log" 2>&1 || FAIL="${FAIL:-cron_$db}"
  current=$(sudo -u odoo psql -d "$db" -Atc 'select count(*) from ir_cron where active')
  before=$(awk -F'|' '$2=="t" {n++} END {print n+0}' "$D/cron_$db.txt")
  log "crons on $db: $current (before: $before)"
  if [[ ",$UP_CSV," == *",+pb_joining,"* ]]; then
    joined=$(sudo -u odoo psql -d "$db" -Atc "select count(*) from ir_cron c join ir_model_data x on x.model='ir.cron' and x.res_id=c.id where x.module='pb_joining' and x.name='cron_joining_daily' and c.active")
    [ "$joined" = 1 ] && [ "$current" = "$((before+1))" ] || FAIL="${FAIL:-cron_$db}"
  fi
done
refresh_assets; lap "crons+assets"
service odoo-server start; sleep 10
DOWN=$(( $(date +%s) - TD ))
log "started: $(systemctl is-active odoo-server), procs $(pgrep -fc '[o]doo-server/odoo-bin')"
for db in $DBS; do
  status=$(curl -Ls -o /dev/null -w '%{http_code}' --max-time 120 "https://$(host_of "$db")/web/login")
  log "warm $db $status"
  [ "$status" = 200 ] || FAIL="${FAIL:-warm_$db}"
done
lap warm
if [ -z "$FAIL" ]; then
  verify
  if [[ ",$UP_CSV," == *",+pb_joining,"* ]]; then
    python3 "$STAGE/.release/joining/verify_logs.py" $DBS >> "$D/run.log" 2>&1 || finish REDACTION_CHECK_FAILED 1
  fi
  lap verify; finish OK 0
fi
finish "FAILED_ON_$FAIL" 1
