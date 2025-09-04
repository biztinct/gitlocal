-- Update all Vietnam salary rules to use fixed amount instead of python compute
-- This ensures compatibility and avoids python compute errors

-- Update all salary rules that have amount_select = 'code' to use 'fix' instead
UPDATE hr_salary_rule 
SET 
    amount_select = 'fix',
    amount_fix = 0.00,
    amount_python_compute = null
WHERE amount_select = 'code'
AND code IN (
    'BASIC', 'HRA', 'DA', 'Travel', 'Meal', 'Medical', 'TRANSPORT', 
    'GROSS', 'SI_EMP', 'HI_EMP', 'UI_EMP', 'PIT', 'NET',
    'SI_COMP', 'HI_COMP', 'UI_COMP'
);

-- Verify the updates
SELECT 
    'UPDATED RULES' as section,
    code,
    name,
    amount_select,
    amount_fix,
    CASE 
        WHEN amount_select = 'fix' AND amount_fix = 0 THEN '✅ Fixed Amount Set'
        ELSE '⚠️ Needs Review'
    END as status
FROM hr_salary_rule 
WHERE code IN (
    'BASIC', 'HRA', 'DA', 'Travel', 'Meal', 'Medical', 'TRANSPORT', 
    'GROSS', 'SI_EMP', 'HI_EMP', 'UI_EMP', 'PIT', 'NET',
    'SI_COMP', 'HI_COMP', 'UI_COMP'
)
ORDER BY sequence;

-- Check if any rules still have python compute
SELECT 
    'REMAINING PYTHON COMPUTE' as section,
    COUNT(*) as rules_with_python_compute,
    CASE 
        WHEN COUNT(*) = 0 THEN '✅ No rules with python compute'
        ELSE '⚠️ ' || COUNT(*) || ' rules still have python compute'
    END as status
FROM hr_salary_rule 
WHERE amount_python_compute IS NOT NULL 
AND amount_python_compute != '';

-- List any remaining rules with python compute (for review)
SELECT 
    'RULES WITH PYTHON COMPUTE' as section,
    code,
    name,
    amount_select,
    amount_python_compute
FROM hr_salary_rule 
WHERE amount_python_compute IS NOT NULL 
AND amount_python_compute != ''
ORDER BY sequence;