-- Migration script to populate salary_structure_name for existing payroll.analytics records
-- This script should be run after upgrading the module to add the new field

-- Update analytics records by matching payslip runs to their structure and formula config
UPDATE payroll_analytics pa
SET salary_structure_name = COALESCE(
    (SELECT hfc.name 
     FROM hr_payslip_run hpr
     JOIN hr_payslip hp ON hp.payslip_run_id = hpr.id
     JOIN hr_payroll_structure hps ON hp.struct_id = hps.id
     LEFT JOIN hr_formula_config hfc ON hfc.structure_id = hps.id
     WHERE hpr.id = pa.payslip_run_id
     LIMIT 1),
    (SELECT hps.name
     FROM hr_payslip_run hpr
     JOIN hr_payslip hp ON hp.payslip_run_id = hpr.id
     JOIN hr_payroll_structure hps ON hp.struct_id = hps.id
     WHERE hpr.id = pa.payslip_run_id
     LIMIT 1)
)
WHERE pa.payslip_run_id IS NOT NULL 
  AND (pa.salary_structure_name IS NULL OR pa.salary_structure_name = '');

-- For analytics records without a payslip_run_id, try to match by date and country
UPDATE payroll_analytics pa
SET salary_structure_name = COALESCE(
    (SELECT hfc.name
     FROM hr_payslip hp
     JOIN hr_payroll_structure hps ON hp.struct_id = hps.id
     LEFT JOIN hr_formula_config hfc ON hfc.structure_id = hps.id
     WHERE hp.date_from >= pa.date_from
       AND hp.date_to <= pa.date_to
       AND hp.state IN ('level2', 'done')
     LIMIT 1),
    (SELECT hps.name
     FROM hr_payslip hp
     JOIN hr_payroll_structure hps ON hp.struct_id = hps.id
     WHERE hp.date_from >= pa.date_from
       AND hp.date_to <= pa.date_to
       AND hp.state IN ('level2', 'done')
     LIMIT 1),
    'Unknown Structure'
)
WHERE (pa.salary_structure_name IS NULL OR pa.salary_structure_name = '');
