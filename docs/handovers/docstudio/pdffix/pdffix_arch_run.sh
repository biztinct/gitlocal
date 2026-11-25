#!/bin/bash
# DOCSTUDIO PDFFIX phase 2: payslips today (live templates, old engine) vs changed templates on the
# old engine and on the patched engine. Root on the server:
#   EV=<folder> NEWBIN=<dir with patched wkhtmltopdf> TPL=<dir with changed xml> bash pdffix_arch_run.sh <db> <slip ids>
set -u
db=$1; SLIPS=$2
REFS=pb_hr_payroll_formula.action_report_payslip_themed,om_hr_payroll.action_report_payslip,pb_hr_payroll_vietnam.action_report_payslip_vietnam
ARCH="pb_hr_payroll_formula.payslip_themed=$TPL/payslip_themed.xml;om_hr_payroll.report_payslip=$TPL/report_payslip_templates.xml;pb_hr_payroll_vietnam.report_payslip_vietnam=$TPL/report_payslip_vietnam_template.xml"
mkdir -p $EV && chown odoo:odoo $EV && chmod 750 $EV
cp /tmp/pdffix2/pdffix_arch_probe.py $EV/ && chown odoo $EV/pdffix_arch_probe.py
sed -e "s#^logfile.*#logfile = $EV/probe-odoo.log#" /etc/odoo-server.conf > $EV/probe.conf; chown odoo $EV/probe.conf; chmod 600 $EV/probe.conf
BASE=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/bin
for run in live-old tpl-old tpl-new; do
  P=$BASE; A=""; case $run in tpl-*) A=$ARCH;; esac; case $run in *-new) P=$NEWBIN:$BASE;; esac
  mkdir -p $EV/$db-$run && chown odoo $EV/$db-$run
  PID0=$(pgrep -f 'odoo-bin -c /etc/odoo-server.conf$' | head -1)
  sudo -u odoo env PATH=$P OUT=$EV/$db-$run SLIPS=$SLIPS REFS=$REFS ARCH="$A" python3 /odoo/odoo-server/odoo-bin shell \
    -c $EV/probe.conf -d $db --no-http --max-cron-threads=0 < $EV/pdffix_arch_probe.py > $EV/$db-$run.out 2>&1
  PID1=$(pgrep -f 'odoo-bin -c /etc/odoo-server.conf$' | head -1)
  UP=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 https://payobook.com/web/login)
  echo "$(date -u +%T) $db $run: $([ "$PID0" = "$PID1" ] && [ "$UP" = 200 ] && echo VALID || echo INVALID) $(grep -E '^PROBE|Error' $EV/$db-$run.out | sed 's/^PROBE //' | tr '\n' ';' | cut -c1-500)"
done
rm -f $EV/probe.conf; echo ARCH-RUN DONE
