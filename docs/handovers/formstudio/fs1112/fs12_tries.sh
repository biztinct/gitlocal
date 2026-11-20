#!/bin/bash
# FS-11/FS-12: try the go-live every 10 minutes (up to N tries). While another deployer's START of
# today is still open, nothing is written and nothing changes (writing our START then would block
# them). Once none is open: our START line, then the go-live script (which re-checks the lock, the
# notes for a HOLD or a new START, the live trees and 15 quiet minutes on rize/payobook, and refuses
# without touching anything when any of those fails). Root, in a systemd-run unit:
#   bash fs12_tries.sh <TS> [N]
TS=$1; N=${2:-24}
EV=/tmp/fs12-$TS
TAG="Claude FORMSTUDIO FS-11/FS-12"
others_open() {
  python3 - "$TAG" <<'PY'
import sys
tag = sys.argv[1]
lines = open('/opt/deploy-notes.md', encoding='utf-8', errors='replace').read().splitlines()
import datetime
today = datetime.datetime.utcnow().strftime('%Y-%m-%d')
base = lambda s: s.split('(')[0].strip().lower()
opens = {}
for l in [x for x in lines if x[:10] == today]:
    parts = [p.strip() for p in l.split('|')]
    if len(parts) < 3 or tag in l:
        continue
    who, what = parts[1], parts[2].upper()
    if what == 'START':
        opens[who] = l
    elif what in ('DONE', 'FAILED', 'VERIFIED', 'ABORTED', 'CANCELLED', 'COMPLETE'):
        for k in list(opens):
            if k == who or base(k) == base(who):
                opens.pop(k)
print(list(opens)[-1] if opens else '')
PY
}
for i in $(seq 1 $N); do
  OTHER=$(others_open)
  if [ -n "$OTHER" ]; then
    echo "$(date -u +%T) try $i: waiting, open START of $OTHER" >> $EV/tries.log
    [ $i -lt $N ] && sleep 600
    R=WAITING-OTHER
    continue
  fi
  if ! grep -q "$TAG | START" /opt/deploy-notes.md; then
    echo "$(date -u '+%Y-%m-%d %H:%M UTC') | $TAG | START | -u pb_form_studio 19.0.1.5.0, pb_form_studio_people 19.0.1.5.0, pb_form_studio_contracts 19.0.1.4.0; -i pb_form_studio_portal 19.0.1.0.0 | payobook,payobook_template,p0clone,rize,sudima | $(cat /tmp/fs12_commit.txt) (origin/fs-11-12 = origin/19.1 9ac8b8fae + FS-11 + FS-12; 3 live trees = origin/19.1, nothing newer on the server). Form builder: fixed sections list their fields; My Payobook page builder (My Profile). Backups x5 (again right before the stop), rehearsal on hidden copies of all five done (payslips identical), go-live only after 15 min with no signed-in activity on rize/payobook, takes /tmp/payobook-studio-deploy.lock, re-reads these notes for a HOLD line right before the stop. ABM untouched; Codex modules untouched." >> /opt/deploy-notes.md
  fi
  bash /tmp/fs12_golive.sh $TS
  R=$(cat $EV/golive.result 2>/dev/null)
  echo "$(date -u +%T) try $i: $R" >> $EV/tries.log
  if [ "$R" = REFUSED-NOTES ] && grep -q '^HOLD' $EV/notes-check.txt; then
    echo "$(date -u +%T) HOLD line in the notes: stopping the tries" >> $EV/tries.log; break
  fi
  case "$R" in
    ACTIVE|REFUSED-LOCK|REFUSED-NOTES) [ $i -lt $N ] && sleep 600 ;;
    *) break ;;
  esac
done
echo "$(date -u +%T) tries finished: $R" >> $EV/tries.log
touch $EV/tries.finished
