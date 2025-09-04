-- Check what salary rules actually exist in the system
SELECT 
    id, 
    name, 
    code, 
    sequence,
    (SELECT name FROM hr_salary_rule_category WHERE id = category_id) as category_name
FROM hr_salary_rule 
ORDER BY sequence, code;

-- Check what rules are in the Vietnam structure
SELECT 
    sr.name as rule_name,
    sr.code as rule_code,
    sr.sequence,
    src.name as category_name
FROM hr_payroll_structure_rule_rel rel
JOIN hr_salary_rule sr ON rel.hr_salary_rule_id = sr.id
JOIN hr_salary_rule_category src ON sr.category_id = src.id
JOIN hr_payroll_structure s ON rel.hr_payroll_structure_id = s.id
WHERE s.code = 'VN_STD'
ORDER BY sr.sequence;

-- Check what structures exist
SELECT id, name, code FROM hr_payroll_structure ORDER BY name;