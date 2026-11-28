#!/bin/bash
# DOCSTUDIO close-out D go-live (RISKY tier; clone of pdffix/pdffix_golive.sh with SWITCH_ENGINE=0 and
# w2/w2_golive.sh's rails). Root inside a systemd-run unit: bash cd_golive.sh <TS>
# Refuses (service untouched) when: lock busy or named by another holder, a HOLD line or another
# deployer's open START today, live trees moved since prep, a server module newer than shipped, a
# release module not installed somewhere, signed-in activity on rize/payobook/sudima in the last 15
# minutes, a backup fails. Then: fresh dumps x5 + counts, stop, per-module scoped rsync of the 12
# trees, per DB -u (one at a time, stop at first failure), cron snapshot repaired, asset purge +
# version bump, start, warm. Any upgrade failure: previous trees back, the failed DB and the DBs
# already done restored from the dumps taken right before the stop, service started, result FAILED.
TS=$1
EV=/tmp/cd-$TS
BK=/odoo/backups/docstudio-close-$TS
STAGE=/tmp/deployCD/addons
ADD=/odoo/odoo-server/addons
ORDER="payobook_template p0clone sudima rize payobook"
MODS=$(cat /tmp/cd_mods.txt)
UPG=$(echo $MODS | tr ' ' ',')
IN=$(echo $MODS | sed "s/\([a-z_0-9]*\)/'\1'/g; s/ /,/g")
TAG="Claude DOCSTUDIO CLOSE"
mkdir -p $EV $BK; chown odoo:odoo $EV; chmod 750 $EV
log() { echo "$(date -u +%T) $*" | tee -a $EV/steps.log; }
result() { echo "$1" > $EV/golive.result; }
rm -f $EV/golive.result
exec 9>>/tmp/payobook-studio-deploy.lock
flock -n 9 || { log "lock busy - refused, nothing changed"; result REFUSED-LOCK; exit 0; }
HOLDER=$(head -c 200 /tmp/payobook-studio-deploy.lock | tr -d '\0')
if [ -n "$HOLDER" ] && ! echo "$HOLDER" | grep -q "^$TAG"; then
  log "lock file names another holder ($HOLDER) - refused, nothing changed"; result REFUSED-LOCK; exit 0
fi
: > /tmp/payobook-studio-deploy.lock
echo "$TAG $(date -u '+%Y-%m-%d %H:%M:%S UTC') pid $$ (go-live)" > /tmp/payobook-studio-deploy.lock
trap ': > /tmp/payobook-studio-deploy.lock; rm -f /tmp/payobook-studio-deploy.lock' EXIT
notes_ok() {
  python3 - "$TAG" > $EV/notes-check.txt <<'PY'
import re, sys, datetime
tag = sys.argv[1]
lines = open('/opt/deploy-notes.md', encoding='utf-8', errors='replace').read().splitlines()
today = datetime.datetime.utcnow().strftime('%Y-%m-%d')
base = lambda s: s.split('(')[0].strip().lower()
opens, hold = {}, None
for l in [x for x in lines if x[:10] == today]:
    parts = [p.strip() for p in l.split('|')]
    if len(parts) < 3 or tag in parts[1]:
        continue
    who, what = parts[1], parts[2].upper()
    if re.search(r'\bHOLD\b', what):
        hold = l
    if what == 'START':
        opens[who] = l
    elif what.startswith(('DONE', 'FAILED', 'VERIFIED', 'ABORTED', 'CANCELLED', 'COMPLETE', 'CALLED OFF')):
        for k in list(opens):
            if k == who or base(k) == base(who):
                opens.pop(k)
print('HOLD ' + hold[:200] if hold else ('OPEN-START ' + list(opens.values())[-1][:200] if opens else 'ok'))
PY
  grep -q '^ok' $EV/notes-check.txt
}
quiet() {
  SINCE=$(date -u -d '15 minutes ago' '+%Y-%m-%d %H:%M:%S')
  awk -v s="$SINCE" '($1" "substr($2,1,8)) >= s' /var/log/odoo/odoo-server.log \
    | grep -E ' INFO (rize|payobook|sudima) werkzeug: ' \
    | grep -E '"(POST|GET) /(web/dataset/|web/action|json/|mail/|web/webclient/load|bizapp|odoo/|web/session/get|my/|my |report/)' \
    | grep -vE 'websocket|/bus/|longpolling' | grep -E 'HTTP/1.[01]" 200 ' > $EV/activity-before-stop.txt
  [ ! -s $EV/activity-before-stop.txt ]
}
notes_ok || { log "deploy notes: $(cat $EV/notes-check.txt) - refused, nothing changed"; result REFUSED-NOTES; exit 0; }
bash /tmp/s2_hashtree.sh $ADD $MODS > $EV/live-trees-now.txt
diff -q $EV/live-trees-now.txt $EV/live-trees-before.txt >/dev/null || { log "live trees moved since prep - refused"; result REFUSED-MOVED; exit 0; }
python3 - "$EV/live-trees-now.txt" "$EV/staged-trees.txt" > $EV/version-check.txt <<'PY'
import sys
def rd(p):
    d = {}
    for line in open(p):
        parts = line.split()
        if len(parts) >= 2 and parts[1] != 'ABSENT':
            d[parts[0]] = tuple(int(x) for x in parts[1].split('.'))
    return d
live, new = rd(sys.argv[1]), rd(sys.argv[2])
bad = [m for m in new if m in live and live[m] >= new[m]]
print('NOT-NEWER ' + ' '.join(bad) if bad else 'ok')
PY
grep -q '^ok' $EV/version-check.txt || { log "$(cat $EV/version-check.txt) (server already at or above the shipped version) - refused"; result REFUSED-NEWER; exit 0; }
[ "$(cat $EV/deps.ok 2>/dev/null)" = yes ] || { log "a release module is not installed on some database (prep) - refused"; result REFUSED-DEPS; exit 0; }
[ "$(cat $EV/base.ok 2>/dev/null)" = yes ] || { log "live trees differ from origin/19.1 (prep) - refused"; result REFUSED-BASE; exit 0; }
quiet || { log "signed-in activity in the last 15 min ($(wc -l < $EV/activity-before-stop.txt) requests, last $(tail -1 $EV/activity-before-stop.txt | cut -c1-19)) - not stopping"; result ACTIVE; exit 0; }
log "quiet since $SINCE UTC; backups x5 + counts + job snapshots"
for db in $ORDER; do
  sudo -u postgres pg_dump -Fc $db > $BK/golive-$db.dump && pg_restore -l $BK/golive-$db.dump > /dev/null \
    || { log "BACKUP FAILED $db - refused, nothing changed"; result REFUSED-BACKUP; exit 0; }
  bash /tmp/cd_counts.sh $db > $EV/counts-before-$db.txt
  sudo -u postgres psql -X -At -d $db -c "select id||','||active::text from ir_cron order by id" > $EV/cron-golive-$db.txt
done
log "backups: $(for db in $ORDER; do echo -n "$db $(stat -c %s $BK/golive-$db.dump) "; done)"
quiet || { log "activity started during the backups - not stopping"; result ACTIVE; exit 0; }
notes_ok || { log "deploy notes just before the stop: $(cat $EV/notes-check.txt) - refused"; result REFUSED-NOTES; exit 0; }
log "still quiet, no HOLD, no open START - stop service"; T0=$(date +%s)
wc -l < /var/log/odoo/odoo-server.log > $EV/log-line-at-stop.txt
service odoo-server stop
for i in $(seq 1 60); do [ "$(ps -eo cmd | grep -c '[o]doo-bin -c /etc/odoo-server.conf$')" = 0 ] && break; sleep 1; done
log "service processes left: $(ps -eo cmd | grep -c '[o]doo-bin -c /etc/odoo-server.conf$')"
for m in $MODS; do mkdir -p $ADD/$m && rsync -a --delete $STAGE/$m/ $ADD/$m/ && chown -R odoo:odoo $ADD/$m; done
bash /tmp/s2_hashtree.sh $ADD $MODS > $EV/live-trees-after.txt
log "rsynced; addons = staged: $(diff -q $EV/live-trees-after.txt $EV/staged-trees.txt >/dev/null && echo yes || echo NO); pb_learn vi_VN.po = staged: $(cmp -s $ADD/pb_learn/i18n/vi_VN.po $STAGE/pb_learn/i18n/vi_VN.po && echo yes || echo NO)"
FAILED=""; DONE_DBS=""
for db in $ORDER; do
  sed -e "s#^logfile.*#logfile = $EV/$db-upgrade.log#" /etc/odoo-server.conf > $EV/up-$db.conf
  chown odoo:odoo $EV/up-$db.conf; chmod 600 $EV/up-$db.conf
  U0=$(date +%s)
  sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c $EV/up-$db.conf -d $db -u $UPG --stop-after-init \
    --no-http --max-cron-threads=0 > $EV/$db-upgrade.out 2>&1
  X=$?; rm -f $EV/up-$db.conf
  sudo -u postgres psql -X -At -d $db -c "select name||'='||state||':'||coalesce(latest_version,'') from ir_module_module where name in ($IN) order by name" > $EV/versions-after-$db.txt
  BADV=$(python3 - $EV/staged-trees.txt $EV/versions-after-$db.txt <<'PY'
import sys
want = {l.split()[0]: l.split()[1] for l in open(sys.argv[1]) if l.strip()}
got = {}
for l in open(sys.argv[2]):
    n, rest = l.strip().split('=', 1); st, v = rest.split(':', 1); got[n] = (st, v)
print(' '.join(m for m, v in want.items() if got.get(m) != ('installed', v)))
PY
)
  log "upgrade $db exit $X in $(( $(date +%s) - U0 )) s; ERROR lines $(grep -cE ' (ERROR|CRITICAL) ' $EV/$db-upgrade.log); not at the shipped version: ${BADV:-none}"
  [ -n "$BADV" ] && [ $X = 0 ] && X=99
  if [ $X != 0 ]; then FAILED=$db; log "STOPPING: $db failed"; break; fi
  DONE_DBS="$DONE_DBS $db"
  sudo -u postgres psql -X -At -d $db -c "INSERT INTO orm_signaling_assets DEFAULT VALUES" \
     -c "DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'" \
     -c "UPDATE ir_config_parameter SET value='docstudio-close-$TS' WHERE key='web.assets.version'" >> $EV/steps.log 2>&1
  sudo -u postgres psql -X -At -d $db -c "select id||','||active::text from ir_cron order by id" > $EV/cron-mid-$db.txt
  ON=$(join -t, <(sort $EV/cron-golive-$db.txt) <(sort $EV/cron-mid-$db.txt) | awk -F, '$2=="false" && $3=="true" {print $1}' | paste -sd, -)
  if [ -n "$ON" ]; then
    sudo -u postgres psql -X -At -d $db -c "UPDATE ir_cron SET active=false WHERE id IN ($ON)" >> $EV/steps.log
    log "$db: switched back off jobs the upgrade re-activated: $ON"
  fi
  NEWJ=$(join -t, -v2 <(sort $EV/cron-golive-$db.txt) <(sort $EV/cron-mid-$db.txt) | paste -sd' ' -)
  [ -n "$NEWJ" ] && log "$db: NEW job rows: $NEWJ"
  bash /tmp/cd_counts.sh $db > $EV/counts-installed-$db.txt
done
if [ -n "$FAILED" ]; then
  log "FAILED on $FAILED - previous trees back, restore:$DONE_DBS $FAILED"
  for m in $MODS; do rm -rf $ADD/$m; done
  tar -C $ADD -xzf $BK/previous-trees.tgz && for m in $MODS; do chown -R odoo:odoo $ADD/$m; done
  bash /tmp/s2_hashtree.sh $ADD $MODS > $EV/live-trees-restored.txt
  log "trees back = before: $(diff -q $EV/live-trees-restored.txt $EV/live-trees-before.txt >/dev/null && echo yes || echo NO)"
  for rdb in $DONE_DBS $FAILED; do
    sudo -u postgres dropdb --force $rdb && sudo -u postgres createdb -O odoo $rdb \
      && cat $BK/golive-$rdb.dump | sudo -u postgres pg_restore -d $rdb > $EV/restore-$rdb.log 2>&1
    sudo -u postgres psql -X -At -d $rdb -c "DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'" >/dev/null
    log "restored $rdb: $(sudo -u postgres psql -X -At -d $rdb -c "select count(*) from hr_employee") employees"
  done
fi
log "start service"
service odoo-server start
for i in $(seq 1 300); do ss -ltn | grep -q ':8069 ' && break; sleep 1; done
log "port 8069 $(ss -ltn | grep -q ':8069 ' && echo listening || echo NOT-LISTENING)"
echo "downtime_seconds $(( $(date +%s) - T0 ))" | tee -a $EV/steps.log
for h in payobook.com payobook_template.payobook.com p0clone.payobook.com rize.payobook.com sudima.payobook.com; do
  log "warm $h: $(curl -s -o /dev/null -m 180 -w '%{http_code}' -H "Host: $h" http://127.0.0.1:8069/web/login)"
done
if [ -n "$FAILED" ]; then result "FAILED $FAILED"; else result DONE; fi
