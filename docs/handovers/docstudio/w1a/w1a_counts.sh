#!/bin/bash
# DOCSTUDIO W1A: read-only counts + checksums of one database. The FORM STUDIO chain
# (/tmp/fs12_counts.sh -> fsd -> te -> s2: employees, contracts, payslips, lines, users, ...) plus
# what this release could touch. "x_" lines are EXPECTED to move (module rows, the Insights entry).
db=$1
bash /tmp/fs12_counts.sh "$db"
q() { sudo -u postgres psql -X -At -d "$db" -c "$1" 2>&1 | tr '\n' ' ' | sed 's/ $//'; }
t() { [ "$(q "select to_regclass('public.$1') is not null")" = t ] && q "select count(*) from $1" || echo "no table"; }
echo "x_docstudio_rows: report_definitions $(t pb_report_definition) excel_layouts $(t pb_excel_layout)"
echo "explorer_views: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, name, user_id)::text, chr(10) order by id),'')) from pb_explorer_view")"
echo "explorer_schedules: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, active)::text, chr(10) order by id),'')) from pb_explorer_schedule")"
echo "mail_queue: $(q "select count(*)||' '||count(*) filter (where state in ('outgoing','exception')) from mail_mail")"
echo "approvals: $(q "select count(*) from biz_approval_request") todos $(q "select count(*) from mail_activity")"
echo "x_insights_entry_groups: $(q "select coalesce(string_agg(g.res_groups_id::text, ',' order by g.res_groups_id),'') from ir_model_data d join pb_sidebar_item_res_groups_rel g on g.pb_sidebar_item_id=d.res_id where d.module='pb_insights_hub' and d.name='item_insights' and d.model='pb.sidebar.item'")"
