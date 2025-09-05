-- Check current analytics and payslip data
-- Run this to understand the current state

-- 1. Check current analytics records
SELECT 
    'CURRENT ANALYTICS' as section,
    id,
    period_name,
    country,
    date_from,
    date_to,
    total_employees,
    total_payroll,
    state
FROM payroll_analytics 
ORDER BY date_from DESC;

-- 2. Check July 2025 payslips
SELECT 
    'JULY 2025 PAYSLIPS' as section,
    COUNT(*) as total_payslips,
    state,
    MIN(date_from) as earliest_date,
    MAX(date_to) as latest_date
FROM hr_payslip 
WHERE date_from >= '2025-07-01' 
AND date_to <= '2025-07-31'
GROUP BY state
ORDER BY state;

-- 3. Check payslip details for Level 2
SELECT 
    'LEVEL 2 PAYSLIP DETAILS' as section,
    p.id as payslip_id,
    p.number,
    e.name as employee_name,
    p.date_from,
    p.date_to,
    p.state,
    s.name as structure_name
FROM hr_payslip p
JOIN hr_employee e ON p.employee_id = e.id
JOIN hr_payroll_structure s ON p.struct_id = s.id
WHERE p.date_from >= '2025-07-01' 
AND p.date_to <= '2025-07-31'
AND p.state = 'level2'
ORDER BY e.name;

-- 4. Check salary rule lines for Level 2 payslips
SELECT 
    'SALARY COMPONENTS' as section,
    COUNT(*) as line_count,
    SUM(CASE WHEN code = 'NET' THEN total ELSE 0 END) as total_net,
    SUM(CASE WHEN code = 'BASIC' THEN total ELSE 0 END) as total_basic
FROM hr_payslip_line pl
JOIN hr_payslip p ON pl.slip_id = p.id
WHERE p.date_from >= '2025-07-01' 
AND p.date_to <= '2025-07-31'
AND p.state = 'level2';

-- 5. Fix the analytics by deleting September record and regenerating
-- DELETE FROM payroll_analytics WHERE period_name LIKE '%September 2025%' AND country = 'VN';

-- After running this query, you can regenerate analytics using the Python script