#!/bin/bash
# INBOX-BULK-BANK: try the go-live every 10 minutes (up to N tries; 24 = 240 min). Clone of
# fs13/fs13_tries.sh. While another deployer's START of today is open, nothing is written and
# nothing changes. Once none is open: our START line, then the go-live script (which re-checks the
# lock, the notes for a HOLD or a new START, the live trees and 15 quiet minutes on rize/payobook/sudima,
# and refuses without touching anything when any of those fails).
# FS-13 addition: the START is ALWAYS closed by this script — DONE, FAILED, or "CALLED OFF (HELD …)"
# when the tries run out or a HOLD line stops them (a CALLED OFF line closes a START for every
# deployer's notes check). Root, in a systemd-run unit:  bash ibb_tries.sh <TS> [N]
TS=$1; N=${2:-24}
EV=/tmp/ibb-$TS
TAG="Claude INBOX-BULK-BANK"
COMMIT=$(cat /tmp/ibb_commit.txt)
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
    note "START | $(cat /tmp/ibb_versions.txt) (cascade to installed dependents) | payobook,payobook_template,p0clone,rize,sudima | $COMMIT (origin/inbox-bulk-bank = origin/19.1 + INBOX-BULK-BANK; 3 live trees = origin/19.1, nothing newer on the server). Approvals inbox: bank-detail requests can be approved several at once after an extra check (Select all N, groups of 50 with progress); switch on the route editor's Safeguards step (administrator only); payment kinds still one at a time. Nothing is approved by this deploy. Backups x5 (again right before the stop), rehearsal on hidden copies of all five done, go-live only after 15 min with no signed-in activity on rize/payobook/sudima, takes /tmp/payobook-studio-deploy.lock, re-reads these notes for a HOLD line right before the stop. ABM untouched; Codex modules untouched."
    STARTED=1
  fi
  bash /tmp/ibb_golive.sh $TS
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
    DONE) note "DONE | $(cat /tmp/ibb_versions.txt) x5 | payobook,payobook_template,p0clone,rize,sudima | $COMMIT; ${DOWN} s down; $(grep -E 'upgrade .* exit' $EV/steps.log | tail -5 | awk '{print $3"="$5"/"$7"s"}' | paste -sd' ' -); asset purge + web.assets.version x5; verification follows in a NOTE line. Backups /odoo/backups/ibb-$TS/. ABM untouched." ;;
    FAILED*) note "FAILED | $R | payobook,payobook_template,p0clone,rize,sudima | $COMMIT; previous trees put back, upgraded databases restored from the dumps taken right before the stop, service started (${DOWN} s down). Evidence $EV." ;;
    *) note "CALLED OFF (HELD, closes the START above) | nothing deployed: $R after $N tries (no 15 quiet minutes on rize/payobook/sudima, a HOLD line, the lock or a newer START) | service untouched, live trees unchanged. Evidence $EV." ;;
  esac
fi
echo "$(date -u +%T) tries finished: $R" >> $EV/tries.log
touch $EV/tries.finished
