-- Fix the combined analytics issue - separate July and August batches
-- This script will delete the combined analytics and create separate ones

-- 1. Delete the incorrect combined analytics (July-August)
DELETE FROM payroll_analytics 
WHERE country = 'VN' 
AND date_from = '2025-07-01' 
AND date_to = '2025-08-31';

-- 2. Check what payslip batches we have
SELECT 
    'CURRENT BATCHES' as section,
    name,
    date_start,
    date_end,
    state,
    (SELECT COUNT(*) FROM hr_payslip WHERE payslip_run_id = hr_payslip_run.id) as payslip_count
FROM hr_payslip_run 
WHERE state = 'level2'
ORDER BY date_start;

-- 3. Check Level 2 payslips by month
SELECT 
    'PAYSLIPS BY MONTH' as section,
    EXTRACT(YEAR FROM date_from) as year,
    EXTRACT(MONTH FROM date_from) as month,
    COUNT(*) as payslip_count,
    MIN(date_from) as earliest_date,
    MAX(date_to) as latest_date
FROM hr_payslip 
WHERE state = 'level2'
GROUP BY EXTRACT(YEAR FROM date_from), EXTRACT(MONTH FROM date_from)
ORDER BY year, month;

-- 4. Create separate analytics records for each month (if they don't exist)

-- July 2025 Analytics
INSERT INTO payroll_analytics (
    period_name,
    country,
    date_from,
    date_to,
    state,
    create_date,
    write_date,
    create_uid,
    write_uid
)
SELECT 
    'July 2025 - VN',
    'VN',
    '2025-07-01',
    '2025-07-31',
    'ready',
    NOW(),
    NOW(),
    1,
    1
WHERE NOT EXISTS (
    SELECT 1 FROM payroll_analytics 
    WHERE country = 'VN' 
    AND date_from = '2025-07-01' 
    AND date_to = '2025-07-31'
);

-- August 2025 Analytics (if August payslips exist)
INSERT INTO payroll_analytics (
    period_name,
    country,
    date_from,
    date_to,
    state,
    create_date,
    write_date,
    create_uid,
    write_uid
)
SELECT 
    'August 2025 - VN',
    'VN',
    '2025-08-01',
    '2025-08-31',
    'ready',
    NOW(),
    NOW(),
    1,
    1
WHERE EXISTS (
    SELECT 1 FROM hr_payslip 
    WHERE state = 'level2' 
    AND date_from >= '2025-08-01' 
    AND date_to <= '2025-08-31'
)
AND NOT EXISTS (
    SELECT 1 FROM payroll_analytics 
    WHERE country = 'VN' 
    AND date_from = '2025-08-01' 
    AND date_to = '2025-08-31'
);

-- 5. Verify the results
SELECT 
    'FINAL ANALYTICS RECORDS' as section,
    period_name,
    date_from,
    date_to,
    state
FROM payroll_analytics 
WHERE country = 'VN'
ORDER BY date_from;