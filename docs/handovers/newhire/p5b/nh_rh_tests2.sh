#!/bin/bash
# NEWHIRE P5b: re-run the test classes that failed on the payobook copy for ENVIRONMENT reasons, with
# the environment fixed and nothing else changed:
#   - the static tests read sibling modules next to pb_new_hire (pb_import_kit, pb_orgchart, pb_pay_scales, pb_updates,
#     pb_people_advanced): a test addons dir holds the staged six + links to the live siblings
#   - the web-page tests call 127.0.0.1: the live conf's "dbfilter = ^%d$" finds no database for that
#     host (404); the test conf has an empty dbfilter
# Copy only. Root: bash nh_rh_tests2.sh <TS>
TS=$1; SRC=payobook
EV=/tmp/newhire-p5b-$TS
COPY=nh_rh_$SRC
T=/tmp/deployNH_t/addons
rm -rf /tmp/deployNH_t && mkdir -p $T && cp -a /tmp/deployNH/addons/. $T/
for m in pb_import_kit pb_orgchart pb_people_advanced pb_pay_scales pb_updates; do ln -s /odoo/odoo-server/addons/$m $T/$m; done
chown -R odoo:odoo /tmp/deployNH_t
sed -e "s#^logfile.*#logfile = $EV/rh-tests2.log#" -e "s#^dbfilter.*#dbfilter = #" -e "s#^addons_path *=.*#addons_path = $T,/odoo/odoo-server/addons#" $EV/rh-$SRC.conf > $EV/rh-tests2.conf
chown odoo:odoo $EV/rh-tests2.conf; chmod 600 $EV/rh-tests2.conf
sudo -u postgres psql -X -At -d $COPY -c "UPDATE ir_mail_server SET active=false" -c "UPDATE ir_cron SET active=false" > /dev/null
T0=$(date +%s)
timeout 1800 sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c $EV/rh-tests2.conf -d $COPY \
  -u pb_new_hire --test-enable \
  --test-tags /pb_new_hire:TestWelcomePage,/pb_new_hire:TestDocsStatic,/pb_new_hire:TestP5aDependants,/pb_new_hire:TestNewHireStatic \
  --stop-after-init --http-port=8297 --gevent-port=8296 --max-cron-threads=0 --log-level=info > $EV/rh-tests2.out 2>&1
X=$?
sudo -u postgres psql -X -At -d $COPY -c "UPDATE ir_cron SET active=false" > /dev/null
echo "$(date -u +%T) [$SRC] environment re-run exit $X in $(( $(date +%s) - T0 )) s; $(grep -hE '[0-9]+ failed, [0-9]+ error' $EV/rh-tests2.log | tail -1 | sed -E 's/^[0-9-]+ [0-9:,]+ [0-9]+ //')" | tee -a $EV/rehearsal.log
grep -hE ': (FAIL|ERROR): ' $EV/rh-tests2.log | sed -E 's/^[0-9-]+ [0-9:,]+ [0-9]+ //' | cut -c1-200 | sort -u | tee -a $EV/rehearsal.log
rm -f $EV/rh-tests2.conf; rm -rf /tmp/deployNH_t
touch $EV/rh-tests2.finished
