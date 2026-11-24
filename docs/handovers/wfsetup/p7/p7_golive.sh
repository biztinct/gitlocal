#!/bin/bash
# WFSETUP P7 go-live (clone of ../p6/p6_golive.sh + ../p5b/wfs_golive.sh): -i pb_workforce_setup on
# payobook_template, p0clone, rize, one at a time (pulls in pb_attendance_policy). NO files ship: the live
# trees must still equal prep (= the commit). Root inside a systemd-run unit: bash p7_golive.sh <TS>
# Refuses (service untouched) when: lock busy, a HOLD line or another deployer's open START, live trees
# moved since prep, no passed rize rehearsal, or signed-in activity on rize/payobook/sudima in the last
# 15 minutes. Fresh dumps of the three right before the stop. Jobs the install re-activates go back off;
# NEW job rows stay as installed except on payobook_template, where they are switched off and their ids
# appended to pb_tenants.template_active_crons (new tenants get them on). First failure: that database
# restored from its dump, sequence stopped, service started, result FAILED.
TS=$1
EV=/tmp/wfsetup-p7-$TS
BK=/odoo/backups/wfsetup-p7-$TS
ADD=/odoo/odoo-server/addons
ORDER="payobook_template p0clone rize"
MODS=$(cat /tmp/p7_mods.txt)
WANTV=$(python3 -c "import ast;print(ast.literal_eval(open('$ADD/pb_workforce_setup/__manifest__.py').read())['version'])")
VSQL="'pb_workforce_setup','pb_workforce_workspace','pb_hr_workforce','pb_attendance_policy'"
TAG="Claude WFSETUP P7"
log() { echo "$(date -u +%T) $*" | tee -a $EV/steps.log; }
result() { echo "$1" > $EV/golive.result; }
pq() { sudo -u postgres psql -X -At -d "$@"; }
rm -f $EV/golive.result
exec 9>/tmp/payobook-studio-deploy.lock
flock -n 9 || { log "lock busy - refused, nothing changed"; result REFUSED-LOCK; exit 0; }
echo "$TAG $(date -u '+%Y-%m-%d %H:%M:%S UTC') pid $$ (go-live; this file is removed when it finishes)" >&9
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
quiet() {
  SINCE=$(date -u -d '15 minutes ago' '+%Y-%m-%d %H:%M:%S')
  awk -v s="$SINCE" '($1" "substr($2,1,8)) >= s' /var/log/odoo/odoo-server.log \
    | grep -E ' INFO (rize|payobook|sudima) werkzeug: ' \
    | grep -E '"(POST|GET) /(web/dataset/|web/action|json/|mail/|web/webclient/load|bizapp|odoo/|web/session/get|my/|my |report/)' \
    | grep -vE 'websocket|/bus/|longpolling' | grep -E 'HTTP/1.[01]" 200 ' > $EV/activity-before-stop.txt
  [ ! -s $EV/activity-before-stop.txt ]
}
notes_ok || { log "deploy notes: $(cat $EV/notes-check.txt) - refused, nothing changed"; result REFUSED-NOTES; exit 0; }
bash /tmp/p7_hashtree.sh $ADD $MODS > $EV/live-trees-now.txt
diff -q $EV/live-trees-now.txt $EV/live-trees-before.txt >/dev/null || { log "live trees moved since prep - refused"; result REFUSED-MOVED; exit 0; }
[ "$(cat $EV/rehearsal-rize.result 2>/dev/null)" = OK ] || { log "no passed rize rehearsal on record - refused"; result REFUSED-REHEARSAL; exit 0; }
if ! quiet; then
  log "signed-in activity in the last 15 min ($(wc -l < $EV/activity-before-stop.txt) requests; last $(tail -1 $EV/activity-before-stop.txt | cut -c1-19)) - not stopping"
  result ACTIVE; exit 0
fi
log "no signed-in activity on rize/payobook/sudima since $SINCE UTC - backups x3 + counts before"
for db in $ORDER; do
  sudo -u postgres pg_dump -Fc $db > $BK/golive-$db.dump && pg_restore -l $BK/golive-$db.dump > /dev/null \
    || { log "BACKUP FAILED $db - refused, nothing changed"; result REFUSED-BACKUP; exit 0; }
  bash /tmp/p7_counts.sh $db > $EV/counts-before-$db.txt
  pq $db -c "select id||','||active::text from ir_cron order by id" > $EV/cron-golive-$db.txt
done
log "backups: $(for db in $ORDER; do echo -n "$db $(ls -l $BK/golive-$db.dump | awk '{print $5}') "; done)"
quiet || { log "activity started during the backups - not stopping"; result ACTIVE; exit 0; }
notes_ok || { log "deploy notes just before the stop: $(cat $EV/notes-check.txt) - refused, nothing changed"; result REFUSED-NOTES; exit 0; }
log "still quiet, no HOLD, no open START - stop service"; T0=$(date +%s)
wc -l < /var/log/odoo/odoo-server.log > $EV/log-line-at-stop.txt
service odoo-server stop
for i in $(seq 1 60); do [ "$(ps -eo cmd | grep -c '[o]doo-bin -c /etc/odoo-server.conf')" = 0 ] && break; sleep 1; done
log "odoo-bin processes: $(ps -eo cmd | grep -c '[o]doo-bin -c /etc/odoo-server.conf'); no files copied (trees = commit)"
FAILED=""
for db in $ORDER; do
  sed -e "s#^logfile.*#logfile = $EV/$db-upgrade.log#" /etc/odoo-server.conf > $EV/up-$db.conf
  chown odoo:odoo $EV/up-$db.conf; chmod 600 $EV/up-$db.conf
  log "install $db -i pb_workforce_setup"
  U0=$(date +%s)
  sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c $EV/up-$db.conf -d $db -i pb_workforce_setup --stop-after-init \
    --no-http --max-cron-threads=0 > $EV/$db-upgrade.out 2>&1
  X=$?
  echo "$db exit $X" >> $EV/exit-sentinels.txt
  log "install $db exit $X in $(( $(date +%s) - U0 )) s; ERROR $(grep -cE ' (ERROR|CRITICAL) ' $EV/$db-upgrade.log); $(pq $db -c "select string_agg(name||'='||state||':'||coalesce(latest_version,''), ' ' order by name) from ir_module_module where name in ($VSQL)")"
  rm -f $EV/up-$db.conf
  NI=$(pq $db -c "select count(*) from ir_module_module where state='installed' and (name='pb_workforce_setup' and latest_version='$WANTV' or name='pb_attendance_policy')")
  [ "$NI" != 2 ] && { log "$db: setup + rules modules installed $NI of 2 - treated as a failure"; X=99; }
  if [ $X != 0 ]; then FAILED="$db"; log "STOPPING the sequence: $db failed"; break; fi
  pq $db -c "INSERT INTO orm_signaling_assets DEFAULT VALUES" \
     -c "DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'" \
     -c "UPDATE ir_config_parameter SET value='wfsetup-p7-$TS' WHERE key='web.assets.version'" >> $EV/steps.log 2>&1
  pq $db -c "select id||','||active::text from ir_cron order by id" > $EV/cron-mid-$db.txt
  ON=$(join -t, <(sort $EV/cron-golive-$db.txt) <(sort $EV/cron-mid-$db.txt) | awk -F, '$2=="false" && $3=="true" {print $1}' | paste -sd, -)
  if [ -n "$ON" ]; then
    pq $db -c "UPDATE ir_cron SET active=false WHERE id IN ($ON)"
    log "$db: switched back off jobs re-activated by the install: $ON"
  fi
  NEWIDS=$(join -t, -v2 <(sort $EV/cron-golive-$db.txt) <(sort $EV/cron-mid-$db.txt) | cut -d, -f1 | sort -n | paste -sd, -)
  [ -n "$NEWIDS" ] && log "$db: NEW job rows after the install: $(pq $db -c "select string_agg(id||' '||(cron_name->>'en_US')||' every '||interval_number||' '||interval_type||' active='||active::text, '; ' order by id) from ir_cron where id in ($NEWIDS)")"
  if [ "$db" = payobook_template ] && [ -n "$NEWIDS" ]; then
    pq $db -c "UPDATE ir_cron SET active=false WHERE id IN ($NEWIDS)" >/dev/null
    OLD=$(pq $db -c "select value from ir_config_parameter where key='pb_tenants.template_active_crons'")
    NEWV=$(python3 -c "import sys; o=[x for x in sys.argv[1].split(',') if x.strip()]; n=[x for x in sys.argv[2].split(',') if x not in o]; print(','.join(o+n))" "$OLD" "$NEWIDS")
    pq $db -c "UPDATE ir_config_parameter SET value='$NEWV', write_date=now() WHERE key='pb_tenants.template_active_crons'" >/dev/null
    log "payobook_template: new job(s) $NEWIDS switched OFF; recorded list for new tenants $(echo "$OLD" | tr ',' '\n' | grep -c .) -> $(pq $db -c "select value from ir_config_parameter where key='pb_tenants.template_active_crons'" | tr ',' '\n' | grep -c .) ids (appended $NEWIDS)"
  fi
  bash /tmp/p7_counts.sh $db > $EV/counts-installed-$db.txt
done
if [ -n "$FAILED" ]; then
  log "FAILED on $FAILED - restoring it from $BK/golive-$FAILED.dump (no files were copied, nothing else to put back)"
  sudo -u postgres dropdb --force $FAILED && sudo -u postgres createdb -O odoo $FAILED \
    && sudo cat $BK/golive-$FAILED.dump | sudo -u postgres pg_restore -d $FAILED > $EV/restore-$FAILED.log 2>&1
  pq $FAILED -c "DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'" >/dev/null
  log "restored $FAILED: employees $(pq $FAILED -c "select count(*) from hr_employee"); $(pq $FAILED -c "select string_agg(name||'='||state||':'||coalesce(latest_version,''), ' ' order by name) from ir_module_module where name in ($VSQL)")"
fi
log "start service"
service odoo-server start
for i in $(seq 1 240); do ss -ltn | grep -q ':8069 ' && break; sleep 1; done
log "port 8069 $(ss -ltn | grep -q ':8069 ' && echo listening || echo NOT-LISTENING)"
echo "downtime_seconds $(( $(date +%s) - T0 ))" | tee -a $EV/steps.log
for h in payobook.com payobook_template.payobook.com p0clone.payobook.com rize.payobook.com sudima.payobook.com; do
  log "warm $h: $(curl -s -o /dev/null -m 120 -w '%{http_code}' -H "Host: $h" http://127.0.0.1:8069/web/login)"
done
mkdir -p /odoo/archives/rize-wfsetup-p7-$TS && cp $BK/golive-rize.dump /odoo/archives/rize-wfsetup-p7-$TS/ 2>/dev/null \
  && log "rize go-live dump kept permanently in /odoo/archives/rize-wfsetup-p7-$TS/"
if [ -n "$FAILED" ]; then result "FAILED $FAILED"; else result DONE; fi
