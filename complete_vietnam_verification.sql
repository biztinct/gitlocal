-- Complete Vietnam Payroll System Verification Script
-- Run this to verify the entire Vietnam payroll setup is working correctly
-- Execute each section and review results

-- =======================================================
-- SECTION 1: VIETNAM SALARY STRUCTURE VERIFICATION
-- =======================================================

-- 1.1 Check Vietnam salary structure exists and rule count
SELECT 
    'STRUCTURE CHECK' as section,
    s.id as structure_id,
    s.name as structure_name,
    s.code as structure_code,
    COUNT(rel.hr_salary_rule_id) as total_rules,
    CASE 
        WHEN COUNT(rel.hr_salary_rule_id) >= 13 THEN '✅ GOOD - Has comprehensive rules'
        WHEN COUNT(rel.hr_salary_rule_id) >= 6 THEN '⚠️ PARTIAL - Has some rules but missing components'
        ELSE '❌ FAIL - Too few rules'
    END as status
FROM hr_payroll_structure s
LEFT JOIN hr_payroll_structure_rule_rel rel ON s.id = rel.hr_payroll_structure_id
WHERE s.code = 'VN_STD'
GROUP BY s.id, s.name, s.code;

-- 1.2 Detailed rule breakdown with sequence order
SELECT 
    'RULES BREAKDOWN' as section,
    sr.sequence,
    sr.code as rule_code,
    sr.name as rule_name,
    src.name as category_name,
    CASE 
        WHEN sr.active = TRUE THEN '✅ Active'
        ELSE '❌ Inactive'
    END as rule_status
FROM hr_payroll_structure_rule_rel rel
JOIN hr_salary_rule sr ON rel.hr_salary_rule_id = sr.id
JOIN hr_salary_rule_category src ON sr.category_id = src.id
WHERE rel.hr_payroll_structure_id = (
    SELECT id FROM hr_payroll_structure WHERE code = 'VN_STD' LIMIT 1
)
ORDER BY sr.sequence;

-- =======================================================
-- SECTION 2: CONTRACT AND PAYSLIP VERIFICATION
-- =======================================================

-- 2.1 Check contracts using Vietnam structure
SELECT 
    'CONTRACT CHECK' as section,
    COUNT(*) as vietnam_contracts,
    CASE 
        WHEN COUNT(*) > 0 THEN '✅ GOOD - Contracts using Vietnam structure'
        ELSE '⚠️ WARNING - No contracts using Vietnam structure yet'
    END as status
FROM hr_contract c
WHERE c.struct_id = (SELECT id FROM hr_payroll_structure WHERE code = 'VN_STD' LIMIT 1);

-- 2.2 Check payslips using Vietnam structure  
SELECT 
    'PAYSLIP CHECK' as section,
    COUNT(*) as vietnam_payslips,
    CASE 
        WHEN COUNT(*) > 0 THEN '✅ GOOD - Payslips using Vietnam structure'
        ELSE '⚠️ WARNING - No payslips using Vietnam structure yet'
    END as status
FROM hr_payslip p
WHERE p.struct_id = (SELECT id FROM hr_payroll_structure WHERE code = 'VN_STD' LIMIT 1);

-- 2.3 Check if any contracts still using BASE structure (should be updated)
SELECT 
    'BASE STRUCTURE CHECK' as section,
    COUNT(*) as contracts_using_base,
    CASE 
        WHEN COUNT(*) = 0 THEN '✅ GOOD - No contracts using old BASE structure'
        ELSE '⚠️ ACTION NEEDED - ' || COUNT(*) || ' contracts still using BASE structure'
    END as status
FROM hr_contract c
WHERE c.struct_id = (SELECT id FROM hr_payroll_structure WHERE code = 'BASE' LIMIT 1);

-- =======================================================  
-- SECTION 3: EMPLOYEE DATA VERIFICATION
-- =======================================================

-- 3.1 List employees with Vietnam contracts
SELECT 
    'EMPLOYEE LIST' as section,
    e.name as employee_name,
    c.name as contract_name,
    s.name as structure_name,
    c.state as contract_state,
    c.wage as basic_wage
FROM hr_contract c
JOIN hr_employee e ON c.employee_id = e.id
JOIN hr_payroll_structure s ON c.struct_id = s.id
WHERE s.code = 'VN_STD'
ORDER BY e.name;

-- =======================================================
-- SECTION 4: PAYROLL ANALYTICS READINESS
-- =======================================================

-- 4.1 Check for Level 2 payslips (analytics ready)
SELECT 
    'ANALYTICS PAYSLIPS' as section,
    COUNT(*) as level2_payslips,
    CASE 
        WHEN COUNT(*) > 0 THEN '✅ READY - Level 2 payslips available for analytics'
        ELSE '⚠️ PENDING - No Level 2 payslips yet'
    END as status
FROM hr_payslip p
WHERE p.state = 'done' 
AND EXISTS (
    SELECT 1 FROM hr_contract c 
    JOIN hr_payroll_structure s ON c.struct_id = s.id 
    WHERE c.id = p.contract_id AND s.code = 'VN_STD'
);

-- 4.2 Recent payslips for analytics (last 3 months)
SELECT 
    'RECENT PAYSLIPS' as section,
    COUNT(*) as recent_payslips,
    MIN(p.date_from) as earliest_date,
    MAX(p.date_to) as latest_date
FROM hr_payslip p
JOIN hr_contract c ON p.contract_id = c.id
JOIN hr_payroll_structure s ON c.struct_id = s.id
WHERE s.code = 'VN_STD'
AND p.date_from >= CURRENT_DATE - INTERVAL '3 months'
ORDER BY COUNT(*) DESC;

-- =======================================================
-- SECTION 5: SALARY RULE CATEGORIES VERIFICATION
-- =======================================================

-- 5.1 Check all required categories exist
SELECT 
    'CATEGORIES CHECK' as section,
    src.code as category_code,
    src.name as category_name,
    COUNT(sr.id) as rules_using_category
FROM hr_salary_rule_category src
LEFT JOIN hr_salary_rule sr ON src.id = sr.category_id
WHERE src.code IN ('BASIC', 'ALW', 'GROSS', 'DED', 'NET', 'COMP')
GROUP BY src.code, src.name
ORDER BY src.code;

-- =======================================================
-- SECTION 6: SYSTEM READINESS SUMMARY
-- =======================================================

-- 6.1 Overall system status summary
SELECT 
    'SYSTEM STATUS SUMMARY' as section,
    (SELECT COUNT(*) FROM hr_payroll_structure WHERE code = 'VN_STD') as vietnam_structure_exists,
    (SELECT COUNT(*) FROM hr_payroll_structure_rule_rel rel 
     WHERE rel.hr_payroll_structure_id = (SELECT id FROM hr_payroll_structure WHERE code = 'VN_STD')) as total_salary_rules,
    (SELECT COUNT(*) FROM hr_contract c 
     WHERE c.struct_id = (SELECT id FROM hr_payroll_structure WHERE code = 'VN_STD')) as vietnam_contracts,
    (SELECT COUNT(*) FROM hr_payslip p 
     WHERE p.struct_id = (SELECT id FROM hr_payroll_structure WHERE code = 'VN_STD')) as vietnam_payslips,
    CASE 
        WHEN (SELECT COUNT(*) FROM hr_payroll_structure_rule_rel rel 
              WHERE rel.hr_payroll_structure_id = (SELECT id FROM hr_payroll_structure WHERE code = 'VN_STD')) >= 13
        THEN '✅ VIETNAM PAYROLL SYSTEM READY FOR PRODUCTION'
        ELSE '⚠️ VIETNAM PAYROLL SYSTEM NEEDS CONFIGURATION'
    END as overall_status;

-- =======================================================
-- EXECUTION INSTRUCTIONS:
-- =======================================================
-- 1. Run this script in your Odoo database
-- 2. Review each section's results
-- 3. If any section shows warnings or failures:
--    - Run the fix_vietnam_structure.sql script
--    - Run the update_vietnam_contracts.sql script
--    - Re-run this verification script
-- 4. When all sections show ✅ status, your Vietnam payroll system is ready!