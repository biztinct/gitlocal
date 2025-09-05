-- Fix analytics records to show correct employee count
-- This will update analytics records with current payslip data

-- 1. Update analytics records with correct employee count from Level 2 payslips
WITH payslip_counts AS (
    SELECT 
        EXTRACT(YEAR FROM date_from) as year,
        EXTRACT(MONTH FROM date_from) as month,
        COUNT(*) as actual_employee_count,
        MIN(date_from) as period_start,
        MAX(date_to) as period_end
    FROM hr_payslip 
    WHERE state = 'level2'
    GROUP BY EXTRACT(YEAR FROM date_from), EXTRACT(MONTH FROM date_from)
)
UPDATE payroll_analytics 
SET total_employees = pc.actual_employee_count,
    write_date = NOW()
FROM payslip_counts pc
WHERE payroll_analytics.country = 'VN'
  AND EXTRACT(YEAR FROM payroll_analytics.date_from) = pc.year
  AND EXTRACT(MONTH FROM payroll_analytics.date_from) = pc.month
  AND payroll_analytics.total_employees != pc.actual_employee_count;

-- 2. Update employee_metrics JSON data
UPDATE payroll_analytics 
SET employee_metrics = jsonb_set(
    COALESCE(employee_metrics::jsonb, '{}'),
    '{total_employees}',
    total_employees::text::jsonb
)
WHERE country = 'VN' 
  AND employee_metrics IS NOT NULL;

-- 3. Verify the fix
SELECT 
    'UPDATED ANALYTICS' as section,
    period_name,
    total_employees,
    total_payroll,
    variance_percentage,
    CASE 
        WHEN total_employees > 1 THEN 'FIXED'
        ELSE 'NEEDS ATTENTION'
    END as status
FROM payroll_analytics 
WHERE country = 'VN'
ORDER BY date_from DESC;