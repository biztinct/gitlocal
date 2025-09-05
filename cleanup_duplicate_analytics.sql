-- Clean up duplicate analytics records and ensure only the most recent one remains
-- This fixes the issue where Approval Queue shows old/incorrect records

-- 1. First, let's see what duplicates exist
SELECT 
    'DUPLICATE ANALYTICS ANALYSIS' as section,
    country,
    date_from,
    date_to,
    COUNT(*) as record_count,
    STRING_AGG(CAST(id AS VARCHAR), ', ' ORDER BY id) as record_ids,
    STRING_AGG(CAST(total_employees AS VARCHAR), ', ' ORDER BY id) as employee_counts,
    STRING_AGG(CAST(total_payroll AS VARCHAR), ', ' ORDER BY id) as payroll_totals
FROM payroll_analytics 
WHERE country = 'VN'
GROUP BY country, date_from, date_to
HAVING COUNT(*) > 1
ORDER BY date_from DESC;

-- 2. Delete duplicate analytics records, keeping only the most recent one (highest ID)
WITH duplicate_analytics AS (
    SELECT 
        id,
        country,
        date_from, 
        date_to,
        total_employees,
        total_payroll,
        ROW_NUMBER() OVER (
            PARTITION BY country, date_from, date_to 
            ORDER BY id DESC  -- Keep the most recent (highest ID)
        ) as rn
    FROM payroll_analytics 
    WHERE country = 'VN'
),
records_to_delete AS (
    SELECT id 
    FROM duplicate_analytics 
    WHERE rn > 1  -- All except the most recent one
)
DELETE FROM payroll_analytics 
WHERE id IN (SELECT id FROM records_to_delete);

-- 3. Verify cleanup - should show only one record per period now
SELECT 
    'AFTER CLEANUP' as section,
    period_name,
    country,
    date_from,
    date_to,
    total_employees,
    total_payroll,
    state,
    id
FROM payroll_analytics 
WHERE country = 'VN'
ORDER BY date_from DESC;

-- 4. Update the remaining analytics records to ensure they have correct state
UPDATE payroll_analytics 
SET state = 'ready',
    write_date = NOW()
WHERE country = 'VN' 
  AND state = 'draft'
  AND total_employees > 0;

-- 5. Final verification
SELECT 
    'FINAL STATUS' as section,
    COUNT(*) as total_records,
    COUNT(CASE WHEN state = 'ready' THEN 1 END) as ready_records,
    COUNT(CASE WHEN state = 'approved' THEN 1 END) as approved_records,
    COUNT(CASE WHEN total_employees > 1 THEN 1 END) as records_with_multiple_employees
FROM payroll_analytics 
WHERE country = 'VN';