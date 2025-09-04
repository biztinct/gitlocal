-- Comprehensive verification script for Vietnam payroll structure
-- Run this after applying the fixes to verify everything is working correctly

-- 1. Check Vietnam salary structure exists and has rules
SELECT 
    s.id as structure_id,
    s.name as structure_name,
    s.code as structure_code,
    COUNT(rel.hr_salary_rule_id) as rule_count
FROM hr_payroll_structure s
LEFT JOIN hr_payroll_structure_rule_rel rel ON s.id = rel.hr_payroll_structure_id
WHERE s.code = 'VN_STD'
GROUP BY s.id, s.name, s.code;

-- 2. List all rules in Vietnam structure with details
SELECT 
    sr.sequence,
    sr.code as rule_code,
    sr.name as rule_name,
    src.name as category_name,
    sr.active
FROM hr_payroll_structure_rule_rel rel
JOIN hr_salary_rule sr ON rel.hr_salary_rule_id = sr.id
JOIN hr_salary_rule_category src ON sr.category_id = src.id
WHERE rel.hr_payroll_structure_id = (
    SELECT id FROM hr_payroll_structure WHERE code = 'VN_STD'
)
ORDER BY sr.sequence;

-- 3. Check which contracts are using Vietnam structure
SELECT 
    COUNT(*) as total_vietnam_contracts
FROM hr_contract c
WHERE c.struct_id = (SELECT id FROM hr_payroll_structure WHERE code = 'VN_STD');

-- 4. Check which payslips are using Vietnam structure
SELECT 
    COUNT(*) as total_vietnam_payslips
FROM hr_payslip p
WHERE p.struct_id = (SELECT id FROM hr_payroll_structure WHERE code = 'VN_STD');

-- 5. Check employees with Vietnam contracts
SELECT 
    e.name as employee_name,
    c.name as contract_name,
    s.name as structure_name,
    c.state as contract_state
FROM hr_contract c
JOIN hr_employee e ON c.employee_id = e.id
JOIN hr_payroll_structure s ON c.struct_id = s.id
WHERE s.code = 'VN_STD'
ORDER BY e.name;

-- 6. Check if there are any contracts still using BASE structure
SELECT 
    COUNT(*) as contracts_still_using_base
FROM hr_contract c
WHERE c.struct_id = (SELECT id FROM hr_payroll_structure WHERE code = 'BASE');

-- 7. Verify salary rule categories exist for Vietnam
SELECT 
    src.name as category_name,
    src.code as category_code
FROM hr_salary_rule_category src
WHERE src.code IN ('BASIC', 'ALW', 'GROSS', 'DED', 'NET', 'COMP')
ORDER BY src.code;