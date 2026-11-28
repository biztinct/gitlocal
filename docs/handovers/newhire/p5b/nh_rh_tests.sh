#!/bin/bash
# NEWHIRE P5b: the pb_new_hire suite (+ pb_people's pay-symbol test) on the REHEARSAL copy of payobook
# (rolled back by the test framework; real data), staged trees first, own ports, no jobs, mail off.
# Clone of ../../wfsetup/p5b/wfs_rh_tests.sh. Root: bash nh_rh_tests.sh <TS>
TS=$1; SRC=payobook
EV=/tmp/newhire-p5b-$TS
COPY=nh_rh_$SRC
T0=$(date +%s)
sed -e "s#^logfile.*#logfile = $EV/rh-tests.log#" $EV/rh-$SRC.conf > $EV/rh-tests.conf; chown odoo:odoo $EV/rh-tests.conf; chmod 600 $EV/rh-tests.conf
sudo -u postgres psql -X -At -d $COPY -c "UPDATE ir_mail_server SET active=false" -c "UPDATE ir_cron SET active=false" > /dev/null
timeout 3600 sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c $EV/rh-tests.conf -d $COPY \
  -u pb_new_hire,pb_people --test-enable --test-tags /pb_new_hire,/pb_people:TestPeoplePaySymbol \
  --stop-after-init --http-port=8297 --gevent-port=8296 --max-cron-threads=0 --log-level=info > $EV/rh-tests.out 2>&1
X=$?
sudo -u postgres psql -X -At -d $COPY -c "UPDATE ir_cron SET active=false" > /dev/null
echo "$(date -u +%T) [$SRC] suites exit $X in $(( $(date +%s) - T0 )) s; $(grep -hE 'tests? .*(failed|error)|Ran [0-9]+ tests|[0-9]+ failed, [0-9]+ error' $EV/rh-tests.log $EV/rh-tests.out | tail -3 | sed -E 's/^[0-9-]+ [0-9:,]+ [0-9]+ //' | tr '\n' ' ')" | tee -a $EV/rehearsal.log
grep -hE '^(FAIL|ERROR):|: (FAIL|ERROR): ' $EV/rh-tests.log | sed -E 's/^[0-9-]+ [0-9:,]+ [0-9]+ //' | cut -c1-200 | sort | uniq | head -40 | tee -a $EV/rehearsal.log
rm -f $EV/rh-tests.conf
touch $EV/rh-tests.finished
