-- Debug variance calculation issues
-- This script helps identify why variance shows -81.9% when values are the same

-- 1. Check all analytics records for Vietnam
SELECT 
    'ANALYTICS RECORDS' as section,
    id,
    period_name,
    country,
    date_from,
    date_to,
    total_employees,
    total_payroll,
    variance_percentage,
    state,
    LENGTH(employee_metrics) as metrics_size,
    LENGTH(salary_components) as components_size,
    LENGTH(comparison_data) as comparison_size
FROM payroll_analytics 
WHERE country = 'VN'
ORDER BY date_from DESC;

-- 2. Check if there are records with identical payroll amounts
SELECT 
    'PAYROLL COMPARISON' as section,
    p1.period_name as current_period,
    p1.total_payroll as current_payroll,
    p2.period_name as previous_period,
    p2.total_payroll as previous_payroll,
    p1.variance_percentage,
    CASE 
        WHEN p1.total_payroll = p2.total_payroll THEN 'IDENTICAL VALUES'
        ELSE 'DIFFERENT VALUES'
    END as comparison_result
FROM payroll_analytics p1
LEFT JOIN payroll_analytics p2 ON p2.country = p1.country 
    AND p2.date_from = p1.date_from - INTERVAL '1 month'
WHERE p1.country = 'VN'
    AND p1.date_from >= '2025-07-01'
ORDER BY p1.date_from DESC;

-- 3. Check if comparison_data contains wrong information
SELECT 
    'COMPARISON DATA ANALYSIS' as section,
    period_name,
    total_payroll,
    variance_percentage,
    CASE 
        WHEN comparison_data IS NOT NULL AND LENGTH(comparison_data) > 10 THEN
            SUBSTRING(comparison_data, 1, 200) || '...'
        ELSE 
            comparison_data
    END as comparison_snippet
FROM payroll_analytics 
WHERE country = 'VN'
    AND date_from >= '2025-07-01'
ORDER BY date_from DESC;

-- 4. Suggested fix - Reset variance to 0 for identical payrolls
UPDATE payroll_analytics 
SET variance_percentage = 0.0
WHERE country = 'VN' 
  AND id IN (
      SELECT p1.id 
      FROM payroll_analytics p1
      JOIN payroll_analytics p2 ON p2.country = p1.country 
          AND p2.date_from = p1.date_from - INTERVAL '1 month'
      WHERE p1.country = 'VN'
        AND p1.total_payroll = p2.total_payroll
        AND p1.total_payroll > 0
  );

-- 5. Final verification
SELECT 
    'AFTER FIX' as section,
    period_name,
    total_payroll,
    variance_percentage,
    CASE 
        WHEN variance_percentage = 0 THEN 'FIXED'
        ELSE 'NEEDS ATTENTION'
    END as status
FROM payroll_analytics 
WHERE country = 'VN'
ORDER BY date_from DESC;