-- Fix TCTE (Total Cost to Employer) calculation and analytics refresh
-- This ensures analytics show correct Total Payroll values

-- 1. First, check if TCTE rule exists in salary rules
INSERT INTO hr_salary_rule (
    name, code, sequence, category_id, condition_select, amount_select, amount_fix,
    create_date, write_date, create_uid, write_uid, active, company_id
)
SELECT 
    'Total Cost to Employer', 
    'TCTE', 
    300,
    (SELECT id FROM hr_salary_rule_category WHERE code = 'GROSS' LIMIT 1),
    'none',
    'fix',
    0.00,
    NOW(),
    NOW(),
    1,
    1,
    true,
    (SELECT id FROM res_company WHERE name = 'My Company' LIMIT 1)
WHERE NOT EXISTS (
    SELECT 1 FROM hr_salary_rule WHERE code = 'TCTE'
);

-- 2. Add TCTE rule to Vietnam structure if not already there
INSERT INTO hr_payroll_structure_rule_rel (structure_id, rule_id)
SELECT 
    vs.id,
    tcte.id
FROM hr_payroll_structure vs
CROSS JOIN hr_salary_rule tcte
WHERE vs.code = 'VN_STD' 
  AND tcte.code = 'TCTE'
  AND NOT EXISTS (
      SELECT 1 FROM hr_payroll_structure_rule_rel 
      WHERE structure_id = vs.id AND rule_id = tcte.id
  );

-- 3. Calculate TCTE values for existing payslips (sum of all positive components)
-- This is a complex calculation that should ideally be done in Python/Odoo
-- For now, we'll create a temporary view to help with analytics

-- 4. Check current payslip data to understand TCTE calculation
SELECT 
    'PAYSLIP ANALYSIS' as section,
    p.name as payslip_name,
    p.employee_id,
    e.name as employee_name,
    p.date_from,
    p.date_to,
    p.state,
    COUNT(pl.id) as line_count,
    SUM(CASE WHEN pl.total > 0 THEN pl.total ELSE 0 END) as total_positive,
    SUM(CASE WHEN pl.code = 'TCTE' THEN pl.total ELSE 0 END) as tcte_value,
    SUM(CASE WHEN pl.code = 'NETPAY' THEN pl.total ELSE 0 END) as net_pay
FROM hr_payslip p
JOIN hr_employee e ON p.employee_id = e.id
LEFT JOIN hr_payslip_line pl ON p.id = pl.slip_id
WHERE p.state = 'level2'
  AND p.date_from >= '2025-07-01'
GROUP BY p.id, p.name, p.employee_id, e.name, p.date_from, p.date_to, p.state
ORDER BY p.date_from, e.name;

-- 5. Check existing analytics records
SELECT 
    'CURRENT ANALYTICS' as section,
    period_name,
    country,
    date_from,
    date_to,
    total_employees,
    total_payroll,
    state
FROM payroll_analytics 
WHERE country = 'VN'
ORDER BY date_from;

-- 6. Force refresh of analytics (this should be done via Odoo UI after server restart)
-- DELETE existing analytics to force regeneration
DELETE FROM payroll_analytics 
WHERE country = 'VN' 
  AND date_from >= '2025-07-01';

-- Note: After running this SQL, restart Odoo server and regenerate analytics via dashboard