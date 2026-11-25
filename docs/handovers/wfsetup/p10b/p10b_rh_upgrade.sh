#!/bin/bash
# WFSETUP P10b: upgrade the hidden copy to the P10b code (new.conf). Root: bash p10b_rh_upgrade.sh <TS> <copy>
EV=/tmp/wfsetup-p10b-$1; COPY=$2
case "$COPY" in zz_wfs_p10b_*) ;; *) echo "copy only"; exit 1;; esac
T0=$(date +%s)
sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c $EV/new.conf -d $COPY -u pb_hr_payroll_formula,pb_clock,pb_attendance_policy,pb_payrun_wizard,pb_workforce_setup,pb_formula_studio,pb_blueprint --stop-after-init --no-http --max-cron-threads=0 > $EV/copy-upgrade.out 2>&1
echo "exit $? in $(( $(date +%s) - T0 )) s; ERROR $(grep -cE ' (ERROR|CRITICAL) ' $EV/copy-odoo.log)"
sudo -u postgres psql -X -At -d $COPY -c "update ir_cron set active=false where active" -c "select name||'='||latest_version from ir_module_module where name in ('pb_hr_payroll_formula','pb_clock','pb_attendance_policy','pb_payrun_wizard','pb_workforce_setup','pb_formula_studio','pb_blueprint') order by 1"
