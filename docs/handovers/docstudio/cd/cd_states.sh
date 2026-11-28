#!/bin/bash
# DOCSTUDIO close-out D: read-only module states + reverse dependencies of the upgraded modules, per DB.
MODS="pb_learn pb_payroll_ai_insights pb_hiring pb_hr_payroll_analytics pb_doc_studio pb_doc_studio_hiring pb_doc_studio_me pb_doc_contracts pb_report_builder pb_excel_layout pb_report_pdf pb_report_pdf_send"
IN=$(echo $MODS | sed "s/\([a-z_0-9]*\)/'\1'/g; s/ /,/g")
for db in payobook payobook_template p0clone rize sudima; do
  echo "== $db: $(sudo -u postgres psql -X -At -d $db -c "select string_agg(name||'='||state||':'||coalesce(latest_version,''), ' ' order by name) from ir_module_module where name in ($IN)")"
  echo "   installed dependents (direct) of upgraded modules: $(sudo -u postgres psql -X -At -d $db -c "select string_agg(distinct m.name, ' ' order by m.name) from ir_module_module_dependency d join ir_module_module m on m.id=d.module_id where d.name in ($IN) and m.state='installed' and m.name not in ($IN)")"
  echo "   active jobs $(sudo -u postgres psql -X -At -d $db -c "select count(*) filter (where active)||'/'||count(*) from ir_cron")"
done
