#!/bin/bash
# Is sudima's employee page hash stable between two runs of the SAME code? (read-only GETs)
EV=/tmp/fs14-$1
sed -e "s#^logfile.*#logfile = $EV/twice-odoo.log#" /etc/odoo-server.conf > $EV/twice.conf; chown odoo:odoo $EV/twice.conf; chmod 600 $EV/twice.conf
for run in 1 2; do
  sudo -u odoo env PROBE_HOST=sudima.payobook.com python3 /odoo/odoo-server/odoo-bin shell -c $EV/twice.conf -d sudima --no-http --max-cron-threads=0 < $EV/fs14_probe.py > $EV/twice-$run.out 2>&1
  echo "run $run: $(grep -E '^PROBE page emp' $EV/twice-$run.out | cut -c1-200)"
done
# who is emp1 (kind of login only, no names)
sudo -u postgres psql -X -At -d sudima -c "select 'share='||u.share::text||' internal_groups='||(select count(*) from res_groups_users_rel r where r.uid=u.id) from hr_employee e join res_users u on u.id=e.user_id where e.active and u.active order by e.id desc limit 1"
rm -f $EV/twice.conf
