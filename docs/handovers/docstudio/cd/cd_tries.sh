#!/bin/bash
# DOCSTUDIO close-out D: wait for other deployers (open START / lock), START line, then the go-live
# every 5 minutes (up to N tries) until it is not refused for activity or the lock; the START is
# always closed (DONE / FAILED / CALLED OFF). Clone of pdffix/pdffix_tries.sh.
# Root in a systemd-run unit:  bash cd_tries.sh <TS> <commit> [N]
TS=$1; COMMIT=$2; N=${3:-48}
EV=/tmp/cd-$TS
TAG="Claude DOCSTUDIO CLOSE"
MODS=$(cat /tmp/cd_mods.txt)
note() { echo "$(date -u '+%Y-%m-%d %H:%M UTC') | $TAG | $1" >> /opt/deploy-notes.md; }
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
lock_free() { flock -n /tmp/payobook-studio-deploy.lock true && [ -z "$(head -c 200 /tmp/payobook-studio-deploy.lock 2>/dev/null | tr -d '\0')" ]; }
mkdir -p $EV
for w in $(seq 1 48); do
  O=$(others_open)
  if [ -z "$O" ] && lock_free; then break; fi
  echo "$(date -u +%T) waiting: open START '$O' / lock '$(head -c 120 /tmp/payobook-studio-deploy.lock 2>/dev/null)'" >> $EV/tries.log
  sleep 300
done
if [ -n "$(others_open)" ] || ! lock_free; then echo "$(date -u +%T) gave up waiting for another deployer" >> $EV/tries.log; echo FINISHED > $EV/tries.done; exit 0; fi
note "START | $(cat /tmp/cd_start.txt)"
R=""
for i in $(seq 1 $N); do
  bash /tmp/cd_golive.sh $TS
  R=$(cat $EV/golive.result 2>/dev/null)
  echo "$(date -u +%T) try $i: $R" >> $EV/tries.log
  case "$R" in
    DONE|FAILED*) break;;
    REFUSED-BACKUP|REFUSED-MOVED|REFUSED-NEWER|REFUSED-DEPS|REFUSED-BASE) break;;
  esac
  sleep 300
done
D=$(grep -o 'downtime_seconds [0-9]*' $EV/steps.log | tail -1 | cut -d' ' -f2)
case "$R" in
  DONE) note "DONE | -u $(echo $MODS | tr ' ' ',') x5 | payobook,payobook_template,p0clone,rize,sudima | $COMMIT; ${D} s down; $(grep -E '^[0-9:]+ upgrade ' $EV/steps.log | tail -5 | sed -E 's/^[0-9:]+ upgrade ([a-z_0-9]+) exit ([0-9]+) in ([0-9]+) s.*/\1=\2\/\3s/' | paste -sd' ' -); asset purge + web.assets.version x5; backups /odoo/backups/docstudio-close-$TS/; verification follows in a NOTE line. ABM untouched.";;
  FAILED*) note "FAILED | $R | restored from the backups taken right before the stop, previous trees back; see $EV/steps.log | ${D} s down. ABM untouched.";;
  *) note "CALLED OFF | last result $R after $i tries; nothing changed. ABM untouched.";;
esac
echo FINISHED > $EV/tries.done
