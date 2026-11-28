#!/bin/bash
# DOCSTUDIO W1B: read-only counts + checksums of one database. The FORM STUDIO chain
# (/tmp/fs12_counts.sh -> fsd -> te -> s2: employees, contracts, payslips, lines, users, ...) plus
# what this release could touch: every letter wording (name/subject/body), every letter, the
# document vault, the mail queue. "x_" lines are EXPECTED to move (the new table, the new column).
db=$1
bash /tmp/fs12_counts.sh "$db"
q() { sudo -u postgres psql -X -At -d "$db" -c "$1" 2>&1 | tr '\n' ' ' | sed 's/ $//'; }
t() { [ "$(q "select to_regclass('public.$1') is not null")" = t ] && q "select count(*) from $1" || echo "no table"; }
echo "letter_templates: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, md5(name::text), md5(coalesce(subject::text,'')), md5(coalesce(body_html::text,'')), active, company_id, letter_type, sequence)::text, chr(10) order by id),'')) from pb_letter_template")"
echo "letter_templates_written: $(q "select coalesce(max(write_date)::text,'-') from pb_letter_template")"
echo "hr_letters: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, state, template_id, employee_id, subject, md5(coalesce(rendered_html,'')), attachment_id, document_id, write_date)::text, chr(10) order by id),'')) from pb_hr_letter")"
echo "employee_documents: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, attachment_id, active, write_date)::text, chr(10) order by id),'')) from pb_employee_document")"
echo "mail_queue: $(q "select count(*)||' '||count(*) filter (where state in ('outgoing','exception'))||' max '||coalesce(max(id),0) from mail_mail")"
echo "x_docstudio: doc_versions $(t pb_doc_version) letter_lang_column $(q "select count(*) from information_schema.columns where table_name='pb_hr_letter' and column_name='lang'") template_studio_columns $(q "select count(*) from information_schema.columns where table_name='pb_letter_template' and column_name like 'pbds_%'")"
echo "x_letter_template_studio_data: $(q "select case when exists(select 1 from information_schema.columns where table_name='pb_letter_template' and column_name='pbds_page') then (select count(*) filter (where pbds_page is not null or pbds_rules is not null or pbds_edited)::text from pb_letter_template) else 'no column' end")"
