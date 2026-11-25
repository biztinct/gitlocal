#!/bin/bash
# DOCSTUDIO PDFFIX go-live (RISKY tier; clone of w2/w2_golive.sh). Root inside a systemd-run unit:
#   bash pdffix_golive.sh <TS>
# Needs: /tmp/deployPF/<module>/ (git archive of the commit), /tmp/pdffix_mods.txt,
#        /odoo/backups/docstudio-pdffix-20261124T1020Z/engine/wkhtmltopdf-0.12.6.1-patched
# Refuses (service untouched) when: lock busy, HOLD or another deployer's open START today,
# signed-in activity on rize/payobook/sudima in the last 15 minutes, a backup fails.
# Switch: per-module scoped rsync of the 7 trees, the patched PDF engine in via dpkg-divert +
# symlink (Ubuntu package kept), per DB -u, cron snapshot repaired, asset purge, start.
# Any upgrade failure: previous trees + old engine back, the failed DB and the DBs already done
# restored from the dumps taken right before the stop, service started, result FAILED.
TS=$1
EV=/tmp/pdffix-golive-$TS
BK=/odoo/backups/docstudio-pdffix-golive-$TS
STAGE=/tmp/deployPF
ADD=/odoo/odoo-server/addons
ENG=/odoo/backups/docstudio-pdffix-20261124T1020Z/engine/wkhtmltopdf-0.12.6.1-patched
NEWBIN=/opt/wkhtmltox-0.12.6.1-3/bin/wkhtmltopdf
ORDER="payobook_template p0clone sudima rize payobook"
MODS=$(cat /tmp/pdffix_mods.txt)
UPG=$(echo $MODS | tr ' ' ',')
TAG="Claude DOCSTUDIO PDFFIX"
mkdir -p $EV $BK; chmod 750 $EV
log() { echo "$(date -u +%T) $*" | tee -a $EV/steps.log; }
result() { echo "$1" > $EV/golive.result; }
rm -f $EV/golive.result
exec 9>>/tmp/payobook-studio-deploy.lock
flock -n 9 || { log "lock busy - refused, nothing changed"; result REFUSED-LOCK; exit 0; }
# other deployers mark the lock by writing their name into the file (and removing it after)
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
quiet || { log "signed-in activity in the last 15 min ($(wc -l < $EV/activity-before-stop.txt) requests, last $(tail -1 $EV/activity-before-stop.txt | cut -c1-19)) - not stopping"; result ACTIVE; exit 0; }
[ -x $ENG ] && $ENG --version | grep -q 'with patched qt' || { log "patched engine missing - refused"; result REFUSED-ENGINE; exit 0; }
log "quiet since $SINCE UTC; backups x5 + job snapshots"
for db in $ORDER; do
  sudo -u postgres pg_dump -Fc $db > $BK/$db.dump && pg_restore -l $BK/$db.dump > /dev/null \
    || { log "BACKUP FAILED $db - refused, nothing changed"; result REFUSED-BACKUP; exit 0; }
  sudo -u postgres psql -X -At -d $db -c "select id||','||active::text from ir_cron order by id" > $EV/cron-before-$db.txt
  sudo -u postgres psql -X -At -d $db -c "select name||'='||state||':'||coalesce(latest_version,'') from ir_module_module where name in ($(echo $MODS | sed "s/\([a-z_]*\)/'\1'/g; s/ /,/g")) order by name" > $EV/versions-before-$db.txt
done
log "backups: $(for db in $ORDER; do echo -n "$db $(stat -c %s $BK/$db.dump) "; done)"
tar -C $ADD -czf $BK/previous-trees.tgz $MODS
quiet || { log "activity started during the backups - not stopping"; result ACTIVE; exit 0; }
notes_ok || { log "deploy notes just before the stop: $(cat $EV/notes-check.txt) - refused"; result REFUSED-NOTES; exit 0; }
log "stop service"; T0=$(date +%s)
service odoo-server stop
for i in $(seq 1 60); do [ "$(ps -eo cmd | grep -c '[o]doo-bin -c /etc/odoo-server.conf$')" = 0 ] && break; sleep 1; done
log "service processes left: $(ps -eo cmd | grep -c '[o]doo-bin -c /etc/odoo-server.conf$')"
for m in $MODS; do mkdir -p $ADD/$m && rsync -a --delete $STAGE/$m/ $ADD/$m/ && chown -R odoo:odoo $ADD/$m; done
log "trees rsynced: $MODS"
install -D -m 755 $ENG $NEWBIN
if [ "$(dpkg-divert --list /usr/bin/wkhtmltopdf | wc -l)" = 0 ]; then
  dpkg-divert --local --rename --divert /usr/bin/wkhtmltopdf.ubuntu --add /usr/bin/wkhtmltopdf >> $EV/steps.log 2>&1
fi
ln -sfn $NEWBIN /usr/bin/wkhtmltopdf
log "engine: $(sudo -u odoo env PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/bin wkhtmltopdf --version 2>&1 | head -1); ubuntu copy $(/usr/bin/wkhtmltopdf.ubuntu --version 2>&1 | head -1)"
FAILED=""; DONE_DBS=""
for db in $ORDER; do
  sed -e "s#^logfile.*#logfile = $EV/$db-upgrade.log#" /etc/odoo-server.conf > $EV/up-$db.conf
  chown odoo:odoo $EV/up-$db.conf; chmod 600 $EV/up-$db.conf
  U0=$(date +%s)
  sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c $EV/up-$db.conf -d $db -u $UPG --stop-after-init \
    --no-http --max-cron-threads=0 > $EV/$db-upgrade.out 2>&1
  X=$?; rm -f $EV/up-$db.conf
  sudo -u postgres psql -X -At -d $db -c "select name||'='||state||':'||coalesce(latest_version,'') from ir_module_module where name in ($(echo $MODS | sed "s/\([a-z_]*\)/'\1'/g; s/ /,/g")) order by name" > $EV/versions-after-$db.txt
  log "upgrade $db exit $X in $(( $(date +%s) - U0 )) s; ERROR lines $(grep -cE ' (ERROR|CRITICAL) ' $EV/$db-upgrade.log); $(tr '\n' ' ' < $EV/versions-after-$db.txt)"
  if [ $X != 0 ]; then FAILED=$db; log "STOPPING: $db failed"; break; fi
  DONE_DBS="$DONE_DBS $db"
  sudo -u postgres psql -X -At -d $db -c "INSERT INTO orm_signaling_assets DEFAULT VALUES" \
     -c "DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'" \
     -c "UPDATE ir_config_parameter SET value='docstudio-pdffix-$TS' WHERE key='web.assets.version'" >> $EV/steps.log 2>&1
  sudo -u postgres psql -X -At -d $db -c "select id||','||active::text from ir_cron order by id" > $EV/cron-after-$db.txt
  ON=$(join -t, <(sort $EV/cron-before-$db.txt) <(sort $EV/cron-after-$db.txt) | awk -F, '$2=="false" && $3=="true" {print $1}' | paste -sd, -)
  if [ -n "$ON" ]; then
    sudo -u postgres psql -X -At -d $db -c "UPDATE ir_cron SET active=false WHERE id IN ($ON)" >> $EV/steps.log
    log "$db: switched back off jobs the upgrade re-activated: $ON"
  fi
  NEWJ=$(join -t, -v2 <(sort $EV/cron-before-$db.txt) <(sort $EV/cron-after-$db.txt) | paste -sd' ' -)
  [ -n "$NEWJ" ] && log "$db: NEW job rows: $NEWJ"
done
if [ -n "$FAILED" ]; then
  log "FAILED on $FAILED - previous trees, old engine, restore:$DONE_DBS $FAILED"
  for m in $MODS; do rm -rf $ADD/$m; done
  tar -C $ADD -xzf $BK/previous-trees.tgz && for m in $MODS; do chown -R odoo:odoo $ADD/$m; done
  rm -f /usr/bin/wkhtmltopdf; dpkg-divert --local --rename --remove /usr/bin/wkhtmltopdf >> $EV/steps.log 2>&1
  log "engine back: $(/usr/bin/wkhtmltopdf --version 2>&1 | head -1)"
  for rdb in $DONE_DBS $FAILED; do
    sudo -u postgres dropdb --force $rdb && sudo -u postgres createdb -O odoo $rdb \
      && cat $BK/$rdb.dump | sudo -u postgres pg_restore -d $rdb > $EV/restore-$rdb.log 2>&1
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
