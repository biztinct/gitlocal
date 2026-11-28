#!/bin/bash
# WFSETUP P7: our START line is already in the notes. Try the go-live every 3 minutes (up to N tries)
# while it answers ACTIVE (signed-in activity in the last 15 min on rize/payobook/sudima); any other
# answer (DONE, FAILED, REFUSED-*) ends the tries. The DONE/FAILED line is written by hand after the
# checks. Root, in a systemd-run unit:  bash p7_tries.sh <TS> [N]   (trimmed clone of ../p5b/wfs_tries.sh)
TS=$1; N=${2:-20}
EV=/tmp/wfsetup-p7-$TS
for i in $(seq 1 $N); do
  bash /tmp/p7_golive.sh $TS
  R=$(cat $EV/golive.result 2>/dev/null)
  echo "$(date -u +%T) try $i: $R" >> $EV/tries.log
  [ "$R" = ACTIVE ] || break
  sleep 180
done
echo "$(date -u +%T) tries finished: $R" >> $EV/tries.log
