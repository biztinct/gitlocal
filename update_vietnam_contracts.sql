-- Update existing contracts to use Vietnam salary structure
-- Run this SQL in your database to update existing contracts

-- First, get the Vietnam structure ID
-- SELECT id, name, code FROM hr_payroll_structure WHERE code = 'VN_STD';

-- Update contracts to use Vietnam structure (replace with actual structure ID)
UPDATE hr_contract 
SET struct_id = (SELECT id FROM hr_payroll_structure WHERE code = 'VN_STD' LIMIT 1)
WHERE struct_id = (SELECT id FROM hr_payroll_structure WHERE code = 'BASE' LIMIT 1);

-- Update existing payslips to use Vietnam structure  
UPDATE hr_payslip 
SET struct_id = (SELECT id FROM hr_payroll_structure WHERE code = 'VN_STD' LIMIT 1)
WHERE struct_id = (SELECT id FROM hr_payroll_structure WHERE code = 'BASE' LIMIT 1);

-- Verify the updates
SELECT 
    c.name as contract_name,
    e.name as employee_name, 
    s.name as structure_name,
    s.code as structure_code
FROM hr_contract c
JOIN hr_employee e ON c.employee_id = e.id
JOIN hr_payroll_structure s ON c.struct_id = s.id
WHERE s.code = 'VN_STD'
LIMIT 10;