#!/bin/bash
# INBOX-BULK-BANK: start the go-live tries only when the rehearsal has finished CLEAN on all five
# copies (exit 0 and 0 ERROR each, sudima approvals done, rize payslips 0 differing).
# Root, in a unit: bash ibb_after_rehearsal.sh <TS> [N]
TS=$1; N=${2:-24}
EV=/tmp/ibb-$TS
for i in $(seq 1 120); do [ -f $EV/rehearsal.done ] && break; sleep 30; done
L=$EV/rehearsal.log
ok=$(grep -cE '\] upgrade exit 0 in [0-9]+ s; ERROR 0, Traceback 0' $L)
pay=$(grep -c 'payslips old vs new: .*DIFFERING 0' $L)
sud=$(grep -c 'every request: bank now = proposal 358, not 0' $EV/sd-approve.out)
if [ ! -f $EV/rehearsal.done ] || [ "$ok" != 5 ] || [ "$pay" != 1 ] || [ "$sud" != 1 ]; then
  echo "$(date -u +%T) rehearsal not clean (upgrades ok $ok/5, rize payslips $pay, sudima $sud): no go-live" >> $EV/tries.log
  touch $EV/tries.finished
  exit 0
fi
echo "$(date -u +%T) rehearsal clean: starting the tries" >> $EV/tries.log
exec bash /tmp/ibb_tries.sh $TS $N
