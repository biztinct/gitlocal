-- Fix duplicate journal entry names issue
-- This script helps identify and resolve duplicate journal entries

-- 1. Identify duplicate journal entry names
SELECT 
    'DUPLICATE JOURNAL ENTRIES' as section,
    name,
    journal_id,
    COUNT(*) as duplicate_count,
    STRING_AGG(CAST(id AS VARCHAR), ', ' ORDER BY id) as entry_ids,
    MIN(date) as earliest_date,
    MAX(date) as latest_date
FROM account_move 
WHERE name LIKE '%VN Payroll%'
   OR name LIKE '%Payroll%'
GROUP BY name, journal_id
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC;

-- 2. Check payslip moves that might be causing conflicts
SELECT 
    'PAYSLIP MOVES ANALYSIS' as section,
    am.name,
    am.date,
    am.ref,
    hp.number as payslip_number,
    hpr.name as batch_name,
    hp.state as payslip_state
FROM account_move am
LEFT JOIN hr_payslip hp ON am.id = hp.move_id
LEFT JOIN hr_payslip_run hpr ON hp.payslip_run_id = hpr.id
WHERE am.ref LIKE '%Payslip%'
   OR am.name LIKE '%Payroll%'
ORDER BY am.date DESC, am.id DESC
LIMIT 20;

-- 3. Update existing moves to have unique names (use with caution)
-- This query shows what would be updated - remove the SELECT and add UPDATE to execute

SELECT 
    'SUGGESTED UPDATES' as section,
    id,
    name as current_name,
    CONCAT(
        CASE 
            WHEN name LIKE '%VN Payroll%' THEN 
                REPLACE(name, 'VN Payroll', 'VN Payroll Entry')
            ELSE 
                name
        END,
        ' - ID:', id
    ) as suggested_new_name,
    date,
    ref
FROM account_move 
WHERE name IN (
    SELECT name 
    FROM account_move 
    GROUP BY name, journal_id 
    HAVING COUNT(*) > 1
)
ORDER BY name, id;

-- 4. If you want to actually fix the duplicates, uncomment and run this:
/*
WITH duplicate_entries AS (
    SELECT 
        id,
        name,
        journal_id,
        ROW_NUMBER() OVER (PARTITION BY name, journal_id ORDER BY id) as rn
    FROM account_move 
    WHERE name LIKE '%Payroll%'
)
UPDATE account_move 
SET name = CONCAT(name, ' (', de.rn, ')')
FROM duplicate_entries de
WHERE account_move.id = de.id 
  AND de.rn > 1;
*/

-- 5. Verify no more duplicates exist
SELECT 
    'VERIFICATION' as section,
    COUNT(*) as total_moves,
    COUNT(DISTINCT name) as unique_names,
    CASE 
        WHEN COUNT(*) = COUNT(DISTINCT name) THEN 'ALL UNIQUE'
        ELSE 'DUPLICATES STILL EXIST'
    END as status
FROM account_move 
WHERE name LIKE '%Payroll%';