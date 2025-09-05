-- Enable automatic analytics generation when payslips reach Level 2
-- This ensures analytics are always generated with correct dates

INSERT INTO ir_config_parameter (key, value, create_date, write_date, create_uid, write_uid)
VALUES (
    'payroll_analytics_approval.auto_generate',
    'True',
    NOW(),
    NOW(),
    1,
    1
)
ON CONFLICT (key) DO UPDATE SET value = 'True', write_date = NOW();