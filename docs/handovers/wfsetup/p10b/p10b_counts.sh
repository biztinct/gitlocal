#!/bin/bash
# WFSETUP P10b (copy of ../p9/p9_counts.sh + pay schemes, their components and payslips, which this
# release must NOT change: the new columns start empty). Read-only. "live_" lines move on their own.
db=$1
bash /tmp/p10b_counts_p9.sh "$db"
q() { sudo -u postgres psql -X -At -d "$db" -c "$1" 2>&1 | tr '\n' ' ' | sed 's/ $//'; }
echo "schemes: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, name, state, company_id, write_date)::text, chr(10) order by id),'')) from hr_formula_config")"
echo "components: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, config_id, code, column_letter, column_type, net_role, appears_on_payslip, excel_formula, default_value, write_date)::text, chr(10) order by id),'')) from hr_formula_rule")"
echo "payslips: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, state, employee_id, date_from, date_to, formula_input_values, write_date)::text, chr(10) order by id),'')) from hr_payslip")"
echo "ot_rules_builtin: $(q "select count(*) from hr_attendance_overtime_rule")"
