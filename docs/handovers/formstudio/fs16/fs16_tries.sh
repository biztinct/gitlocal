#!/bin/bash
# FS-16: try the go-live every 10 minutes (up to N tries; 24 = 240 min). Clone of
# fs1112/fs12_tries.sh. While another deployer's START of today is open, nothing is written and
# nothing changes. Once none is open: our START line, then the go-live script (which re-checks the
# lock, the notes for a HOLD or a new START, the live trees and 15 quiet minutes on rize/payobook/sudima,
# and refuses without touching anything when any of those fails).
# FS-16 addition: the START is ALWAYS closed by this script — DONE, FAILED, or "CALLED OFF (HELD …)"
# when the tries run out or a HOLD line stops them (a CALLED OFF line closes a START for every
# deployer's notes check). Root, in a systemd-run unit:  bash fs16_tries.sh <TS> [N]
TS=$1; N=${2:-24}
EV=/tmp/fs16-$TS
TAG="Claude FORMSTUDIO FS-16"
COMMIT=$(cat /tmp/fs16_commit.txt)
note() { echo "$(date -u '+%Y-%m-%d %H:%M UTC') | $TAG | $1" >> /opt/deploy-notes.md; }
others_open() {
  python3 - "$TAG" <<'PY'
import sys, datetime
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
STARTED=""
R=""
for i in $(seq 1 $N); do
  OTHER=$(others_open)
  if [ -n "$OTHER" ]; then
    echo "$(date -u +%T) try $i: waiting, open START of $OTHER" >> $EV/tries.log
    [ $i -lt $N ] && sleep 600
    R=WAITING-OTHER
    continue
  fi
  if [ -z "$STARTED" ]; then
    note "START | -u pb_hr_payroll_vietnam 19.0.1.2.5, pb_employee_form_tidy 19.0.1.4.1, pb_form_studio_people 19.0.1.8.1, pb_people_advanced 19.0.1.2.0, pb_bank_ocr 19.0.1.6.1, pb_employee_bank_panel 19.0.1.1.1 (cascade: every installed module that depends on the Vietnam payroll module) | payobook,payobook_template,p0clone,rize,sudima | $COMMIT (origin/19.1 + FS-16; the 6 live trees = origin/19.1 fb1e86add, nothing newer on the server). People > Add employee sends bank details for a second person's approval (never to the old boxes); the Form builder no longer lists the fields that cannot come back; 15 dead Vietnam employee fields deleted (re-proved: 0 values, 0 readers on all five). Backups x5 (again right before the stop), rehearsal on hidden copies of all five done, go-live only after 15 min with no signed-in activity on rize/payobook/sudima, takes /tmp/payobook-studio-deploy.lock and removes it after, re-reads these notes for a HOLD line right before the stop. ABM untouched."
    STARTED=1
  fi
  bash /tmp/fs16_golive.sh $TS
  R=$(cat $EV/golive.result 2>/dev/null)
  echo "$(date -u +%T) try $i: $R" >> $EV/tries.log
  if [ "$R" = REFUSED-NOTES ] && grep -q '^HOLD' $EV/notes-check.txt; then
    echo "$(date -u +%T) HOLD line in the notes: stopping the tries" >> $EV/tries.log; R="HELD-BY-HOLD"; break
  fi
  case "$R" in
    ACTIVE|REFUSED-LOCK|REFUSED-NOTES) [ $i -lt $N ] && sleep 600 ;;
    *) break ;;
  esac
done
DOWN=$(grep -E '^downtime_seconds' $EV/steps.log 2>/dev/null | tail -1 | awk '{print $2}')
if [ -n "$STARTED" ]; then
  case "$R" in
    DONE) note "DONE | -u pb_hr_payroll_vietnam, pb_employee_form_tidy, pb_form_studio_people, pb_people_advanced, pb_bank_ocr, pb_employee_bank_panel x5 | payobook,payobook_template,p0clone,rize,sudima | $COMMIT; ${DOWN} s down; $(grep -E 'upgrade .* exit' $EV/steps.log | tail -5 | awk '{print $3"="$5"/"$7"s"}' | paste -sd' ' -); asset purge + web.assets.version x5; verification follows in a NOTE line. Backups /odoo/backups/fs16-$TS/. ABM untouched." ;;
    FAILED*) note "FAILED | $R | payobook,payobook_template,p0clone,rize,sudima | $COMMIT; previous trees put back, upgraded databases restored from the dumps taken right before the stop, service started (${DOWN} s down). Evidence $EV." ;;
    *) note "CALLED OFF (HELD, closes the START above) | nothing deployed: $R after $N tries (no 15 quiet minutes on rize/payobook/sudima, a HOLD line, the lock or a newer START) | service untouched, live trees unchanged. Evidence $EV." ;;
  esac
fi
echo "$(date -u +%T) tries finished: $R" >> $EV/tries.log
# FS-16: the lock file this go-live took is removed when nobody holds it any more
if flock -n /tmp/payobook-studio-deploy.lock true; then rm -f /tmp/payobook-studio-deploy.lock; echo "$(date -u +%T) lock file removed" >> $EV/tries.log; fi
touch $EV/tries.finished
