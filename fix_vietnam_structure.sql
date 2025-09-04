-- Fix Vietnam Standard Payroll structure by adding missing salary rules
-- This adds all the rules that should be in the Vietnam structure

-- First, get the Vietnam structure ID
-- SELECT id FROM hr_payroll_structure WHERE code = 'VN_STD';

-- Clear existing rules and add all rules we want
DELETE FROM hr_payroll_structure_rule_rel WHERE hr_payroll_structure_id = (
    SELECT id FROM hr_payroll_structure WHERE code = 'VN_STD'
);

-- Add Basic Salary rules
INSERT INTO hr_payroll_structure_rule_rel (hr_payroll_structure_id, hr_salary_rule_id)
SELECT 
    (SELECT id FROM hr_payroll_structure WHERE code = 'VN_STD'),
    id
FROM hr_salary_rule 
WHERE code IN ('BASIC', 'HRA', 'DA', 'Travel', 'Meal', 'Medical');

-- Add Transport Allowance (our new rule)
INSERT INTO hr_payroll_structure_rule_rel (hr_payroll_structure_id, hr_salary_rule_id)
SELECT 
    (SELECT id FROM hr_payroll_structure WHERE code = 'VN_STD'),
    id
FROM hr_salary_rule 
WHERE code = 'TRANSPORT' AND sequence = 13;

-- Add Gross and Net
INSERT INTO hr_payroll_structure_rule_rel (hr_payroll_structure_id, hr_salary_rule_id)
SELECT 
    (SELECT id FROM hr_payroll_structure WHERE code = 'VN_STD'),
    id
FROM hr_salary_rule 
WHERE code IN ('GROSS', 'NET') AND sequence IN (100, 200);

-- Add our new insurance rules (Employee)
INSERT INTO hr_payroll_structure_rule_rel (hr_payroll_structure_id, hr_salary_rule_id)
SELECT 
    (SELECT id FROM hr_payroll_structure WHERE code = 'VN_STD'),
    id
FROM hr_salary_rule 
WHERE code IN ('SI_EMP', 'HI_EMP', 'UI_EMP', 'PIT') 
AND sequence BETWEEN 101 AND 104;

-- Add our new insurance rules (Company - for analytics)
INSERT INTO hr_payroll_structure_rule_rel (hr_payroll_structure_id, hr_salary_rule_id)
SELECT 
    (SELECT id FROM hr_payroll_structure WHERE code = 'VN_STD'),
    id
FROM hr_salary_rule 
WHERE code IN ('SI_COMP', 'HI_COMP', 'UI_COMP') 
AND sequence BETWEEN 201 AND 203;

-- Verify what we added
SELECT 
    sr.name,
    sr.code,
    sr.sequence,
    src.name as category
FROM hr_payroll_structure_rule_rel rel
JOIN hr_salary_rule sr ON rel.hr_salary_rule_id = sr.id
JOIN hr_salary_rule_category src ON sr.category_id = src.id
WHERE rel.hr_payroll_structure_id = (
    SELECT id FROM hr_payroll_structure WHERE code = 'VN_STD'
)
ORDER BY sr.sequence;