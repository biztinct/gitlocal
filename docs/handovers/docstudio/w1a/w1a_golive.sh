#!/bin/bash
# DOCSTUDIO W1A go-live (clone of formstudio/fs16/fs16_golive.sh): -i pb_report_builder,pb_excel_layout
# -u pb_explorer per database; the cron snapshot switches back any job the upgrade re-activates.
# Root inside a systemd-run unit: bash w1a_golive.sh <TS>
# Refuses (service untouched) when: lock busy, a HOLD line or another deployer's open START after
# our START in the deploy notes, live trees moved since prep, a server module newer than shipped,
# or signed-in activity on rize/payobook/sudima in the last 15 minutes.
# Fresh dumps x5 right before the stop. If an upgrade fails: previous trees back, the failed database
# AND the databases already upgraded in this run restored from those dumps, service started, result FAILED.
TS=$1
EV=/tmp/w1a-$TS
BK=/odoo/backups/docstudio-w1a-$TS
STAGE=/tmp/deployW1A/addons
ADD=/odoo/odoo-server/addons
ORDER="payobook_template p0clone sudima rize payobook"
MODS=$(cat /tmp/w1a_mods.txt)
INS=pb_report_builder,pb_excel_layout
UPD=pb_explorer
TAG="Claude DOCSTUDIO W1A"
log() { echo "$(date -u +%T) $*" | tee -a $EV/steps.log; }
result() { echo "$1" > $EV/golive.result; }
rm -f $EV/golive.result
exec 9>/tmp/payobook-studio-deploy.lock
flock -n 9 || { log "lock busy - refused, nothing changed"; result REFUSED-LOCK; exit 0; }
notes_ok() {
  python3 - "$TAG" > $EV/notes-check.txt <<'PY'
import re, sys
tag = sys.argv[1]
lines = open('/opt/deploy-notes.md', encoding='utf-8', errors='replace').read().splitlines()
start = max((i for i, l in enumerate(lines) if tag in l and '| START |' in l), default=None)
if start is None:
    print('NO-START'); raise SystemExit
after = lines[start + 1:]
hold = [l for l in after if re.search(r'\bHOLD\b', l, re.I) and tag not in (l.split('|') + ['', ''])[1]]
opens = {}
base = lambda s: s.split('(')[0].strip().lower()
# another deployer's START still open TODAY blocks too, before or after ours
today = lines[start][:10]
for l in [x for x in lines if x[:10] == today]:
    parts = [p.strip() for p in l.split('|')]
    if len(parts) < 3 or tag in parts[1]:
        continue
    who, what = parts[1], parts[2].upper()
    if what == 'START':
        opens[who] = l
    elif what.startswith(('DONE', 'FAILED', 'VERIFIED', 'ABORTED', 'CANCELLED', 'COMPLETE', 'CALLED OFF')):
        for k in list(opens):
            if k == who or base(k) == base(who):
                opens.pop(k)
if hold:
    print('HOLD ' + hold[-1][:200])
elif opens:
    print('OPEN-START ' + list(opens.values())[-1][:200])
else:
    print('ok')
PY
  grep -q '^ok' $EV/notes-check.txt
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
bad = [m for m in new if m in live and live[m] > new[m]]
print('NEWER-ON-SERVER ' + ' '.join(bad) if bad else 'ok')
PY
grep -q '^ok' $EV/version-check.txt || { log "$(cat $EV/version-check.txt) - refused"; result REFUSED-NEWER; exit 0; }
sudo -u odoo python3 -c 'import openpyxl, lxml.etree' > $EV/libs.txt 2>&1 || { log "server python libraries missing ($(tail -1 $EV/libs.txt)) - refused"; result REFUSED-LIBS; exit 0; }
log "python libraries openpyxl + lxml present for the service user"
quiet() {
  SINCE=$(date -u -d '15 minutes ago' '+%Y-%m-%d %H:%M:%S')
  awk -v s="$SINCE" '($1" "substr($2,1,8)) >= s' /var/log/odoo/odoo-server.log \
    | grep -E ' INFO (rize|payobook|sudima) werkzeug: ' \
    | grep -E '"(POST|GET) /(web/dataset/|web/action|json/|mail/|web/webclient/load|bizapp|odoo/|web/session/get|my/|my |report/)' \
    | grep -vE 'websocket|/bus/|longpolling' | grep -E 'HTTP/1.[01]" 200 ' > $EV/activity-before-stop.txt
  [ ! -s $EV/activity-before-stop.txt ]
}
if ! quiet; then
  log "signed-in activity in the last 15 min ($(wc -l < $EV/activity-before-stop.txt) requests; last $(tail -1 $EV/activity-before-stop.txt | cut -c1-19)) - not stopping"
  result ACTIVE; exit 0
fi
log "no signed-in activity on rize/payobook/sudima since $SINCE UTC - backups x5 + counts before"
for db in $ORDER; do
  sudo -u postgres pg_dump -Fc $db > $BK/golive-$db.dump && pg_restore -l $BK/golive-$db.dump > /dev/null \
    || { log "BACKUP FAILED $db - refused, nothing changed"; result REFUSED-BACKUP; exit 0; }
  bash /tmp/w1a_counts.sh $db > $EV/counts-before-$db.txt
  sudo -u postgres psql -X -At -d $db -c "select id||','||active::text from ir_cron order by id" > $EV/cron-golive-$db.txt
done
log "backups: $(for db in $ORDER; do echo -n "$db $(ls -l $BK/golive-$db.dump | awk '{print $5}') "; done)"
quiet || { log "activity started during the backups - not stopping"; result ACTIVE; exit 0; }
notes_ok || { log "deploy notes just before the stop: $(cat $EV/notes-check.txt) - refused, nothing changed"; result REFUSED-NOTES; exit 0; }
log "still quiet, no HOLD, no open START - stop service"; T0=$(date +%s)
wc -l < /var/log/odoo/odoo-server.log > $EV/log-line-at-stop.txt
service odoo-server stop
for i in $(seq 1 60); do [ "$(ps -eo cmd | grep -c '[o]doo-bin -c /etc/odoo-server.conf')" = 0 ] && break; sleep 1; done
log "odoo-bin processes: $(ps -eo cmd | grep -c '[o]doo-bin -c /etc/odoo-server.conf')"
for m in $MODS; do mkdir -p $ADD/$m && rsync -a --delete $STAGE/$m/ $ADD/$m/ && chown -R odoo:odoo $ADD/$m; done
bash /tmp/s2_hashtree.sh $ADD $MODS > $EV/live-trees-after.txt
log "rsynced; addons = staged: $(diff -q $EV/live-trees-after.txt $EV/staged-trees.txt >/dev/null && echo yes || echo NO)"
FAILED=""; DONE_DBS=""
for db in $ORDER; do
  sed -e "s#^logfile.*#logfile = $EV/$db-upgrade.log#" /etc/odoo-server.conf > $EV/up-$db.conf
  chown odoo:odoo $EV/up-$db.conf; chmod 600 $EV/up-$db.conf
  log "upgrade $db -i $INS -u $UPD"
  U0=$(date +%s)
  sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c $EV/up-$db.conf -d $db -i $INS -u $UPD --stop-after-init \
    --no-http --max-cron-threads=0 > $EV/$db-upgrade.out 2>&1
  X=$?
  log "upgrade $db exit $X in $(( $(date +%s) - U0 )) s; ERROR $(grep -cE ' (ERROR|CRITICAL) ' $EV/$db-upgrade.log); $(sudo -u postgres psql -X -At -d $db -c "select string_agg(name||'='||state, ' ' order by name) from ir_module_module where name in ('pb_explorer','pb_report_builder','pb_excel_layout')")"
  rm -f $EV/up-$db.conf
  NI=$(sudo -u postgres psql -X -At -d $db -c "select count(*) from ir_module_module where name in ('pb_explorer','pb_report_builder','pb_excel_layout') and state='installed'")
  [ "$NI" != 3 ] && { log "$db: only $NI of the 3 modules installed - treated as a failure"; X=99; }
  if [ $X != 0 ]; then FAILED="$db"; log "STOPPING the sequence: $db failed"; break; fi
  DONE_DBS="$DONE_DBS $db"
  sudo -u postgres psql -X -At -d $db -c "INSERT INTO orm_signaling_assets DEFAULT VALUES" \
     -c "DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'" \
     -c "UPDATE ir_config_parameter SET value='docstudio-w1a-$TS' WHERE key='web.assets.version'" >> $EV/steps.log 2>&1
  sudo -u postgres psql -X -At -d $db -c "select id||','||active::text from ir_cron order by id" > $EV/cron-mid-$db.txt
  ON=$(join -t, <(sort $EV/cron-golive-$db.txt) <(sort $EV/cron-mid-$db.txt) | awk -F, '$2=="false" && $3=="true" {print $1}' | paste -sd, -)
  if [ -n "$ON" ]; then
    sudo -u postgres psql -X -At -d $db -c "UPDATE ir_cron SET active=false WHERE id IN ($ON)"
    log "$db: switched back off jobs re-activated by the upgrade: $ON"
  fi
  NEWJ=$(join -t, -v2 <(sort $EV/cron-golive-$db.txt) <(sort $EV/cron-mid-$db.txt) | paste -sd' ' -)
  [ -n "$NEWJ" ] && log "$db: NEW job rows after the upgrade: $NEWJ"
  bash /tmp/w1a_counts.sh $db > $EV/counts-installed-$db.txt
done
if [ -n "$FAILED" ]; then
  log "FAILED on $FAILED - putting back previous trees and restoring:$DONE_DBS $FAILED"
  for m in $MODS; do rm -rf $ADD/$m; done
  tar -C $ADD -xzf $BK/previous-trees.tgz && chown -R odoo:odoo $ADD/pb_explorer
  bash /tmp/s2_hashtree.sh $ADD $MODS > $EV/live-trees-restored.txt
  log "trees back = before: $(diff -q $EV/live-trees-restored.txt $EV/live-trees-before.txt >/dev/null && echo yes || echo NO)"
  for rdb in $DONE_DBS $FAILED; do
    sudo -u postgres dropdb --force $rdb && sudo -u postgres createdb -O odoo $rdb \
      && sudo cat $BK/golive-$rdb.dump | sudo -u postgres pg_restore -d $rdb > $EV/restore-$rdb.log 2>&1
    sudo -u postgres psql -X -At -d $rdb -c "DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'" >/dev/null
    log "restored $rdb: employees $(sudo -u postgres psql -X -At -d $rdb -c "select count(*) from hr_employee"); $(sudo -u postgres psql -X -At -d $rdb -c "select string_agg(name||'='||state||':'||coalesce(latest_version,''), ' ' order by name) from ir_module_module where name in ('pb_explorer','pb_report_builder','pb_excel_layout')")"
  done
fi
log "start service"
service odoo-server start
for i in $(seq 1 240); do ss -ltn | grep -q ':8069 ' && break; sleep 1; done
log "port 8069 $(ss -ltn | grep -q ':8069 ' && echo listening || echo NOT-LISTENING)"
echo "downtime_seconds $(( $(date +%s) - T0 ))" | tee -a $EV/steps.log
for h in payobook.com payobook_template.payobook.com p0clone.payobook.com rize.payobook.com sudima.payobook.com; do
  log "warm $h: $(curl -s -o /dev/null -m 120 -w '%{http_code}' -H "Host: $h" http://127.0.0.1:8069/web/login)"
done
if [ -n "$FAILED" ]; then result "FAILED $FAILED"; else result DONE; fi
