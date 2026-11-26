#!/bin/bash
# DOCSTUDIO close-out D: read-only counts + checksums of one database (clone of w2/w2_counts.sh).
# The FORM STUDIO chain (/tmp/fs12_counts.sh) plus what this release could touch. "x_" lines are
# EXPECTED to move: x_letter_template_names (Z3 ships Vietnamese/Indonesian names of the two
# built-in offer letters), x_analytics_print_menu (Z2 takes the three broken PDFs off the Print menu).
db=$1
bash /tmp/fs12_counts.sh "$db"
q() { sudo -u postgres psql -X -At -d "$db" -c "$1" 2>&1 | tr '\n' ' ' | sed 's/ $//'; }
t() { [ "$(q "select to_regclass('public.$1') is not null")" = t ] && q "select count(*) from $1" || echo "no table"; }
echo "letter_templates_wording: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, md5(coalesce(subject::text,'')), md5(coalesce(body_html::text,'')), active, company_id, letter_type, sequence)::text, chr(10) order by id),'')) from pb_letter_template")"
echo "letter_templates_written: $(q "select coalesce(max(write_date)::text,'-') from pb_letter_template")"
echo "letter_template_names_en: $(q "select md5(coalesce(string_agg(row(id, name->>'en_US')::text, chr(10) order by id),'')) from pb_letter_template")"
echo "x_letter_template_names: $(q "select md5(coalesce(string_agg(row(id, name::text)::text, chr(10) order by id),'')) from pb_letter_template")"
echo "doc_versions: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, lang, md5(coalesce(body_html::text,'')))::text, chr(10) order by id),'')) from pb_doc_version")"
echo "hr_letters: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, state, template_id, employee_id, subject, md5(coalesce(rendered_html,'')), attachment_id, document_id, write_date)::text, chr(10) order by id),'')) from pb_hr_letter")"
echo "employee_documents: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, attachment_id, active, write_date)::text, chr(10) order by id),'')) from pb_employee_document")"
echo "hiring_offers: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, state, letter_template_id, md5(coalesce(rendered_html::text,'')), attachment_id, write_date)::text, chr(10) order by id),'')) from pb_hiring_offer")"
echo "certificates: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, state, letter_id, write_date)::text, chr(10) order by id),'')) from pb_me_certificate")"
echo "mail_queue: $(q "select count(*)||' '||count(*) filter (where state in ('outgoing','exception'))||' max '||coalesce(max(id),0) from mail_mail")"
echo "saved_reports: $(q "select count(*) from pb_report_definition") explorer_views: $(q "select count(*) from pb_explorer_view") explorer_schedules: $(q "select count(*)||' active '||count(*) filter (where active) from pb_explorer_schedule") excel_layouts: $(q "select count(*) from pb_excel_layout") pdf_looks: $(t pb_report_pdf_look)"
echo "learn_progress: $(t learn_progress) events $(t learn_event) feedback $(t learn_feedback)"
echo "x_analytics_print_menu: $(q "select string_agg(report_name||'='||coalesce(binding_model_id::text,'none'), ' ' order by report_name) from ir_act_report_xml where report_name like 'pb_hr_payroll_analytics.report_%'")"
