-- FS-16 re-proof, READ ONLY: the 15 dead Vietnam employee fields.
-- Prints: val (stored non-empty values), txt (text mentions anywhere), fk (rows pointing at the field rows), detail lines.
\set QUIET on
\pset footer off
SET default_transaction_read_only = on;
SET statement_timeout = '600s';
\set names '{vn_foreign_insurance_exempt,vn_si_number,vn_si_effective_date,vn_hi_number,vn_hi_effective_date,vn_ui_number,vn_ui_effective_date,vn_tax_table_id,vn_tax_effective_date,vn_employer_insurance_cost,vn_employee_insurance_cost,vn_total_insurance_contribution,vn_personal_tax_rate,vn_monthly_tax_allowance,vn_dependent_tax_allowance}'
\set pat '[[:<:]](vn_foreign_insurance_exempt|vn_si_number|vn_si_effective_date|vn_hi_number|vn_hi_effective_date|vn_ui_number|vn_ui_effective_date|vn_tax_table_id|vn_tax_effective_date|vn_employer_insurance_cost|vn_employee_insurance_cost|vn_total_insurance_contribution|vn_personal_tax_rate|vn_monthly_tax_allowance|vn_dependent_tax_allowance)[[:>:]]'

SELECT 'db|' || current_database();
SELECT 'employees|' || count(*) FROM hr_employee;
-- 1. columns that exist and their stored non-empty values
SELECT 'col|' || column_name || '|' || data_type FROM information_schema.columns
 WHERE table_schema='public' AND table_name='hr_employee' AND column_name = ANY(:'names'::text[]) ORDER BY 1;
SELECT format('SELECT %L || %L || count(*) FROM hr_employee WHERE %I IS NOT NULL AND %I::text NOT IN (%L, %L)',
              'val|', column_name || '|', column_name, column_name, '', 'false')
  FROM information_schema.columns
 WHERE table_schema='public' AND table_name='hr_employee' AND column_name = ANY(:'names'::text[]) ORDER BY column_name
\gexec
-- 2. every text mention in every base table
SELECT format('SELECT %L || m[1] || %L || count(*) FROM %I.%I, regexp_matches(%I::text, %L, %L) m WHERE %I::text ~ %L GROUP BY m[1]',
              'txt|' || c.table_name || '.' || c.column_name || '|', '|', c.table_schema, c.table_name,
              c.column_name, :'pat', 'g', c.column_name, :'pat')
  FROM information_schema.columns c
  JOIN information_schema.tables t ON t.table_schema = c.table_schema AND t.table_name = c.table_name
 WHERE c.table_schema = 'public' AND t.table_type = 'BASE TABLE'
   AND c.data_type IN ('text', 'character varying', 'jsonb', 'json')
 ORDER BY c.table_name, c.column_name
\gexec
-- 3. the field rows and every row of any table pointing at them
SELECT 'field|' || id || '|' || model || '|' || name || '|' || coalesce(store::text,'') || '|' || coalesce(state,'')
  FROM ir_model_fields WHERE name = ANY(:'names'::text[]) ORDER BY model, name;
SELECT format('SELECT %L || f.model || %L || f.name || %L || count(*) FROM %s x JOIN ir_model_fields f ON f.id = x.%I WHERE f.name = ANY(%L::text[]) GROUP BY f.model, f.name',
              'fk|' || c.conrelid::regclass::text || '.' || a.attname || '|', '.', '|', c.conrelid::regclass::text, a.attname, :'names')
  FROM pg_constraint c
  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
 WHERE c.contype = 'f' AND c.confrelid = 'ir_model_fields'::regclass
 ORDER BY 1
\gexec
-- 4. details for the places that matter
SELECT 'view|' || v.id || '|' || v.model || '|' || coalesce(v.key,'') || '|' || coalesce(d.module || '.' || d.name, 'NO-XMLID') || '|' || v.active::text
  FROM ir_ui_view v LEFT JOIN ir_model_data d ON d.model = 'ir.ui.view' AND d.res_id = v.id
 WHERE v.arch_db::text ~ :'pat' ORDER BY v.id;
SELECT 'modfield|' || model || '.' || name || '|' || coalesce(depends,'') || '|' || coalesce(related,'')
  FROM ir_model_fields WHERE (coalesce(depends,'') ~ :'pat' OR coalesce(related,'') ~ :'pat' OR coalesce(compute,'') ~ :'pat');
SELECT 'filter|' || id || '|' || model_id || '|' || coalesce(name::text,'') FROM ir_filters
 WHERE coalesce(domain,'') ~ :'pat' OR coalesce(context,'') ~ :'pat' OR coalesce(sort,'') ~ :'pat';
SELECT 'imd|' || module || '.' || name FROM ir_model_data WHERE name ~ :'pat' ORDER BY 1;
SELECT 'mod|' || name || '|' || state || '|' || coalesce(latest_version,'') FROM ir_module_module
 WHERE name IN ('pb_hr_payroll_vietnam','pb_employee_form_tidy','pb_form_studio_people','pb_people_advanced','pb_bank_ocr','pb_form_studio','pb_records','pb_employee_bank_panel','pb_demo','pb_form_studio_portal','pb_learn','pb_onboarding');
