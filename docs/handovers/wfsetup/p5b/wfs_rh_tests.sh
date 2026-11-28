#!/bin/bash
# WFSETUP P5b: the suites of the P5a/P5c reports on the REHEARSAL copy (rolled back by the test
# framework), staged trees first, own ports, no jobs. Root: bash wfs_rh_tests.sh <TS> [src]
TS=$1; SRC=${2:-sudima}
EV=/tmp/wfsetup-$TS
COPY=wfs_rh_$SRC
T0=$(date +%s)
sed -e "s#^logfile.*#logfile = $EV/rh-tests.log#" $EV/rh-$SRC.conf > $EV/rh-tests.conf; chown odoo:odoo $EV/rh-tests.conf; chmod 600 $EV/rh-tests.conf
sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c $EV/rh-tests.conf -d $COPY \
  -u pb_workforce_setup,pb_workforce_workspace,pb_attendance_policy,pb_shift_patterns \
  --test-enable --test-tags /pb_workforce_setup,/pb_workforce_workspace,/pb_attendance_policy,/pb_shift_patterns \
  --stop-after-init --http-port=8297 --gevent-port=8296 --max-cron-threads=0 --log-level=info > $EV/rh-tests.out 2>&1
X=$?
sudo -u postgres psql -X -At -d $COPY -c "UPDATE ir_cron SET active=false" > /dev/null
echo "$(date -u +%T) [$SRC] suites exit $X in $(( $(date +%s) - T0 )) s; $(grep -hE 'tests? .*(failed|error)|Ran [0-9]+ tests|[0-9]+ failed, [0-9]+ error' $EV/rh-tests.log $EV/rh-tests.out | tail -3 | sed -E 's/^[0-9-]+ [0-9:,]+ [0-9]+ //' | tr '\n' ' ')" | tee -a $EV/rehearsal.log
grep -hE '^(FAIL|ERROR):|: (FAIL|ERROR): ' $EV/rh-tests.log | sed -E 's/^[0-9-]+ [0-9:,]+ [0-9]+ //' | cut -c1-200 | sort | uniq | head -30 | tee -a $EV/rehearsal.log
rm -f $EV/rh-tests.conf
