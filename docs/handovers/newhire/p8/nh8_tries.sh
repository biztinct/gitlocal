#!/bin/bash
# NEWHIRE P8: try the go-live every 10 minutes (up to N tries; 12 = 120 min, the handover's limit).
# Clone of ../p6/nh6_tries.sh. While another deployer's START of today is open, nothing
# is written and nothing changes. Once none is open: our START line, then the go-live script (which
# re-checks the lock, the notes for a HOLD or a new START, the live trees and 15 quiet minutes on
# rize/payobook/sudima, and refuses without touching anything when any of those fails).
# The START is ALWAYS closed by this script - DONE, FAILED, or "CALLED OFF (HELD ...)" when the tries
# run out or a HOLD line stops them. Root, in a systemd-run unit:  bash nh8_tries.sh <TS> [N]
TS=$1; N=${2:-12}
EV=/tmp/newhire-p8-$TS
TAG="Claude NEWHIRE P8"
COMMIT=$(cat /tmp/nh8_commit.txt)
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
    note "START | -u $(awk '$1=="pb_new_hire" || $1=="pb_form_studio_portal" {printf "%s %s, ", $1, $2}' $EV/staged-trees.txt)on all five; pb_scheme_map and biz_access files only (Python, screens, translations; versions unchanged), loaded by the restart | payobook,payobook_template,p0clone,rize,sudima | $COMMIT on 19.1. Add employee: pay scheme follows the country with a choice when there are several; Mapping: Suggest who pays each team; Access: Print a new sign-in slip; HR managers: New joiners board + My Payobook page builder (own company); checklist by country of work; laptop handed over ticks its step; one tax reminder. No data change in this release (the rize team mapping follows separately, owner-ordered). Backups x5 (again right before the stop), rehearsals on hidden rize + payobook copies passed, go-live only after 15 min with no signed-in activity on rize/payobook/sudima, takes /tmp/payobook-studio-deploy.lock and removes it after, re-reads these notes for a HOLD line right before the stop. ABM untouched."
    STARTED=1
  fi
  bash /tmp/nh8_golive.sh $TS
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
    DONE) note "DONE | -u pb_new_hire,pb_form_studio_portal x5 (+ files of pb_scheme_map, biz_access) | payobook,payobook_template,p0clone,rize,sudima | $COMMIT; ${DOWN} s down; $(grep -E 'upgrade .* exit' $EV/steps.log | tail -5 | awk '{print $3"="$5"/"$7"s"}' | paste -sd' ' -); asset purge + web.assets.version x5; verification follows in a NOTE line. Backups /odoo/backups/newhire-p8-$TS/. ABM untouched." ;;
    FAILED*) note "FAILED | $R | payobook,payobook_template,p0clone,rize,sudima | $COMMIT; previous trees put back, upgraded databases restored from the dumps taken right before the stop, service started (${DOWN} s down). Evidence $EV." ;;
    *) note "CALLED OFF (HELD, closes the START above) | nothing deployed: $R after $N tries (no 15 quiet minutes on rize/payobook/sudima, a HOLD line, the lock or a newer START) | service untouched, live trees unchanged. Evidence $EV." ;;
  esac
fi
echo "$(date -u +%T) tries finished: $R" >> $EV/tries.log
if flock -n /tmp/payobook-studio-deploy.lock true; then rm -f /tmp/payobook-studio-deploy.lock; echo "$(date -u +%T) lock file removed" >> $EV/tries.log; fi
touch $EV/tries.finished
