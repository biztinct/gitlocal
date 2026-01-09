-- Cleanup script for advantage templates seeded by pb_hr_payroll_indonesia
-- This removes the templates and any contract advantage lines that reference them.
-- Review the code list before running.

BEGIN;

CREATE TEMP TABLE target_templates AS
    SELECT DISTINCT t.id
    FROM hr_contract_advantage_template t
    LEFT JOIN ir_model_data imd
        ON imd.model = 'hr.contract.advantage.template'
        AND imd.res_id = t.id
    WHERE t.code IN (
        'FIXALL1', 'FIXALL2', 'COMMIS', 'SIGBON',
        'TUNJSR', 'TUNJDK', 'TUNJSK', 'SEVAPP', 'LAINALL',
        'DEDUC1', 'DEDUC2', 'DEDUC3', 'KOPER', 'PINJAM', 'CICIL', 'LAINDED'
    )
    OR (imd.module = 'pb_hr_payroll_indonesia' AND imd.name LIKE 'advantage_template_%');

SELECT
    (SELECT COUNT(*) FROM target_templates) AS template_count,
    (SELECT COUNT(*) FROM hr_contract_advantage WHERE advantage_template_id IN (SELECT id FROM target_templates)) AS advantage_line_count;

DELETE FROM hr_contract_advantage
WHERE advantage_template_id IN (SELECT id FROM target_templates);

DELETE FROM ir_model_data
WHERE model = 'hr.contract.advantage.template'
  AND res_id IN (SELECT id FROM target_templates);

DELETE FROM hr_contract_advantage_template
WHERE id IN (SELECT id FROM target_templates);

DROP TABLE target_templates;

COMMIT;
