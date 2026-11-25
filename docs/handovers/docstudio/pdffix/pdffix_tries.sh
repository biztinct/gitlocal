#!/bin/bash
# DOCSTUDIO PDFFIX: START line, then the go-live every 5 minutes (up to N tries) until it is not
# refused for activity or the lock; the START is always closed (DONE / FAILED / CALLED OFF).
# Root in a systemd-run unit:  bash pdffix_tries.sh <TS> <commit> [N]
TS=$1; COMMIT=$2; N=${3:-36}
EV=/tmp/pdffix-golive-$TS
TAG="Claude DOCSTUDIO PDFFIX"
MODS=$(cat /tmp/pdffix_mods.txt)
note() { echo "$(date -u '+%Y-%m-%d %H:%M UTC') | $TAG | $1" >> /opt/deploy-notes.md; }
ROLLBACK="rollback: sudo service odoo-server stop; sudo rm /usr/bin/wkhtmltopdf; sudo dpkg-divert --local --rename --remove /usr/bin/wkhtmltopdf; sudo service odoo-server start (old engine back; templates are engine-proof)"
others_open() {
  python3 - "$TAG" <<'PY'
import re, sys, datetime
tag = sys.argv[1]
lines = open('/opt/deploy-notes.md', encoding='utf-8', errors='replace').read().splitlines()
today = datetime.datetime.utcnow().strftime('%Y-%m-%d')
base = lambda s: s.split('(')[0].strip().lower()
opens = {}
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
print(list(opens)[-1] if opens else '')
PY
}
mkdir -p $EV
for w in $(seq 1 48); do
  O=$(others_open)
  if [ -z "$O" ] && flock -n /tmp/payobook-studio-deploy.lock true; then break; fi
  echo "$(date -u +%T) waiting: open START '$O' / lock" >> $EV/tries.log
  sleep 300
done
[ -n "$(others_open)" ] && { echo "$(date -u +%T) gave up waiting for another deployer" >> $EV/tries.log; echo FINISHED > $EV/tries.done; exit 0; }
START_TEXT=${START_TEXT:-$(cat /tmp/pdffix_start.txt)}
note "START | $START_TEXT"
R=""
for i in $(seq 1 $N); do
  SWITCH_ENGINE=${SWITCH_ENGINE:-1} bash /tmp/pdffix_golive.sh $TS
  R=$(cat $EV/golive.result 2>/dev/null)
  echo "$(date -u +%T) try $i: $R" >> $EV/tries.log
  case "$R" in
    DONE|FAILED*) break;;
    REFUSED-BACKUP|REFUSED-ENGINE) break;;
  esac
  sleep 300
done
D=$(grep -o 'downtime_seconds [0-9]*' $EV/steps.log | tail -1 | cut -d' ' -f2)
case "$R" in
  DONE) note "DONE | -u $MODS x5 | payobook,payobook_template,p0clone,rize,sudima | $COMMIT; ${D} s down; backups /odoo/backups/docstudio-pdffix-golive-$TS/; verification follows in a NOTE line. $ROLLBACK. ABM untouched.";;
  FAILED*) note "FAILED | $R | restored from backups, old engine and previous trees back; see $EV/steps.log | ${D} s down";;
  *) note "CALLED OFF | last result $R after $i tries; nothing changed";;
esac
echo FINISHED > $EV/tries.done
