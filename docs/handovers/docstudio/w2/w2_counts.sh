#!/bin/bash
# DOCSTUDIO W2: read-only counts + checksums of one database (clone of w1b/w1b_counts.sh). The FORM
# STUDIO chain (/tmp/fs12_counts.sh -> fsd -> te -> s2) plus what this release could touch: the
# letter wording of every template that existed before (rows the new modules add are listed
# separately), letters, the document vault, offers, certificates, the mail queue, saved reports /
# Explorer views / schedules. "x_" lines are EXPECTED to move (new tables, columns, shipped rows).
db=$1
bash /tmp/fs12_counts.sh "$db"
q() { sudo -u postgres psql -X -At -d "$db" -c "$1" 2>&1 | tr '\n' ' ' | sed 's/ $//'; }
col() { [ "$(q "select count(*) from information_schema.columns where table_name='$1' and column_name='$2'")" = 1 ] && echo yes || echo no; }
t() { [ "$(q "select to_regclass('public.$1') is not null")" = t ] && q "select count(*) from $1" || echo "no table"; }
NEWMODS="'pb_doc_contracts','pb_doc_studio_hiring','pb_doc_studio_me','pb_report_pdf','pb_report_pdf_send'"
OLD="id not in (select res_id from ir_model_data where model='pb.letter.template' and module in ($NEWMODS))"
echo "letter_templates_old: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, md5(name::text), md5(coalesce(subject::text,'')), md5(coalesce(body_html::text,'')), active, company_id, letter_type, sequence)::text, chr(10) order by id),'')) from pb_letter_template where $OLD")"
echo "letter_templates_written_old: $(q "select coalesce(max(write_date)::text,'-') from pb_letter_template where $OLD")"
echo "x_letter_templates_new: $(q "select count(*)||' '||coalesce(string_agg(t.id||':'||d.module||'.'||d.name, ' ' order by t.id),'') from pb_letter_template t join ir_model_data d on d.model='pb.letter.template' and d.res_id=t.id and d.module in ($NEWMODS)")"
echo "hr_letters: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, state, template_id, employee_id, subject, md5(coalesce(rendered_html,'')), attachment_id, document_id, write_date)::text, chr(10) order by id),'')) from pb_hr_letter")"
echo "employee_documents: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, attachment_id, active, write_date)::text, chr(10) order by id),'')) from pb_employee_document")"
echo "hiring_offers: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, state, letter_template_id, md5(coalesce(rendered_html::text,'')), attachment_id, write_date)::text, chr(10) order by id),'')) from pb_hiring_offer")"
echo "certificates: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, state, letter_id, write_date)::text, chr(10) order by id),'')) from pb_me_certificate")"
echo "mail_queue: $(q "select count(*)||' '||count(*) filter (where state in ('outgoing','exception'))||' max '||coalesce(max(id),0) from mail_mail")"
echo "saved_reports: $(q "select count(*) from pb_report_definition") explorer_views: $(q "select count(*) from pb_explorer_view") explorer_schedules: $(q "select count(*)||' active '||count(*) filter (where active) from pb_explorer_schedule") excel_layouts: $(q "select count(*) from pb_excel_layout")"
echo "x_docstudio_w2: pdf_looks $(t pb_report_pdf_look) schedule_pdf_column $(col pb_explorer_schedule pbrp_pdf) offer_lang_columns $(col pb_hiring_offer pbds_lang)/$(col pb_hiring_offer pbds_letter_lang) document_contract_columns $(col pb_employee_document pbdc_contract_id)/$(col pb_employee_document pbdc_version) template_sample_column $(col pb_letter_template pbdc_sample)"
