-- =================================================================
-- PAYROLL ANALYTICS DEMO SQL
-- Comprehensive demo data for Analytics Approval Dashboard
-- =================================================================

-- Clear existing demo data (optional - remove if you want to keep existing data)
-- DELETE FROM payroll_analytics WHERE period_name LIKE '%Demo%';

-- =================================================================
-- DEMO RECORD 1: INDONESIA - READY FOR APPROVAL
-- Shows: Ready state, high employee count, variance analysis, anomalies
-- =================================================================

INSERT INTO payroll_analytics (
    id,
    period_name,
    date_from,
    date_to,
    country,
    state,
    employee_metrics,
    salary_components,
    comparison_data,
    anomaly_alerts,
    total_employees,
    total_payroll,
    average_salary,
    variance_percentage,
    preview_record_count,
    preview_total_amount,
    currency_id,
    create_date,
    write_date,
    create_uid,
    write_uid
) VALUES (
    101,
    'December 2024 - Indonesia Demo',
    '2024-12-01',
    '2024-12-31',
    'ID',
    'ready',
    '{"total_employees": 85, "total_payroll": 1250000000, "average_salary": 14705882, "departments": {"Engineering": 35, "Sales": 20, "Marketing": 15, "HR": 8, "Finance": 7}, "positions": {"Software Engineer": 25, "Sales Executive": 15, "Marketing Specialist": 12}}',
    '{"BASIC": {"total": 850000000, "average": 10000000, "count": 85, "name": "Basic Salary"}, "BPJS_KES_EMP": {"total": 12500000, "average": 147059, "count": 85, "name": "BPJS Healthcare (Employee)"}, "BPJS_JHT_EMP": {"total": 17000000, "average": 200000, "count": 85, "name": "Old Age Fund (Employee)"}, "BPJS_JP_EMP": {"total": 8500000, "average": 100000, "count": 85, "name": "Pension (Employee)"}, "MONPIT": {"total": 125000000, "average": 1470588, "count": 85, "name": "Income Tax"}, "NETPAY": {"total": 1087000000, "average": 12788235, "count": 85, "name": "Net Pay"}}',
    '{"previous_month_total": 1150000000, "variance": {"BASIC": 8.7, "BPJS_KES_EMP": 5.2, "BPJS_JHT_EMP": 12.3, "MONPIT": 15.6, "NETPAY": 9.4}, "trend": "increasing", "previous_month": {"BASIC": {"total": 780000000, "average": 9200000}}}',
    '[{"type": "variance", "component": "BPJS_JHT_EMP", "component_name": "Old Age Fund (Employee)", "variance": 12.3, "severity": "medium", "message": "Old Age Fund (Employee) shows 12.3% increase from last month"}, {"type": "variance", "component": "MONPIT", "component_name": "Income Tax", "variance": 15.6, "severity": "medium", "message": "Income Tax shows 15.6% increase from last month"}]',
    85,
    1250000000,
    14705882,
    8.7,
    85,
    1250000000,
    1,
    NOW(),
    NOW(),
    1,
    1
);

-- =================================================================
-- DEMO RECORD 2: VIETNAM - APPROVED
-- Shows: Approved state, moderate employee count, stable growth
-- =================================================================

INSERT INTO payroll_analytics (
    id,
    period_name,
    date_from,
    date_to,
    country,
    state,
    employee_metrics,
    salary_components,
    comparison_data,
    anomaly_alerts,
    total_employees,
    total_payroll,
    average_salary,
    variance_percentage,
    preview_record_count,
    preview_total_amount,
    currency_id,
    create_date,
    write_date,
    create_uid,
    write_uid
) VALUES (
    102,
    'November 2024 - Vietnam Demo',
    '2024-11-01',
    '2024-11-30',
    'VN',
    'approved',
    '{"total_employees": 62, "total_payroll": 850000000, "average_salary": 13709677, "departments": {"Development": 28, "Operations": 18, "Support": 10, "Admin": 6}, "positions": {"Developer": 20, "Operations Manager": 12, "Support Specialist": 15}}',
    '{"BASIC": {"total": 620000000, "average": 10000000, "count": 62, "name": "Basic Salary"}, "ALLOWANCES": {"total": 93000000, "average": 1500000, "count": 62, "name": "Allowances"}, "SOCIAL_INS": {"total": 31000000, "average": 500000, "count": 62, "name": "Social Insurance"}, "PIT": {"total": 85000000, "average": 1370968, "count": 62, "name": "Personal Income Tax"}, "NETPAY": {"total": 727000000, "average": 11725806, "count": 62, "name": "Net Pay"}}',
    '{"previous_month_total": 820000000, "variance": {"BASIC": 3.7, "ALLOWANCES": 2.1, "SOCIAL_INS": 4.2, "PIT": 5.8, "NETPAY": 3.2}, "trend": "stable", "previous_month": {"BASIC": {"total": 598000000, "average": 9645161}}}',
    '[{"type": "variance", "component": "PIT", "component_name": "Personal Income Tax", "variance": 5.8, "severity": "low", "message": "Personal Income Tax shows 5.8% increase from last month"}]',
    62,
    850000000,
    13709677,
    3.7,
    62,
    850000000,
    1,
    NOW() - INTERVAL '1 month',
    NOW() - INTERVAL '1 month',
    1,
    1
);

-- =================================================================
-- DEMO RECORD 3: INDIA - READY FOR APPROVAL
-- Shows: Large employee base, complex salary components, high variance alerts
-- =================================================================

INSERT INTO payroll_analytics (
    id,
    period_name,
    date_from,
    date_to,
    country,
    state,
    employee_metrics,
    salary_components,
    comparison_data,
    anomaly_alerts,
    total_employees,
    total_payroll,
    average_salary,
    variance_percentage,
    preview_record_count,
    preview_total_amount,
    currency_id,
    create_date,
    write_date,
    create_uid,
    write_uid
) VALUES (
    103,
    'December 2024 - India Demo',
    '2024-12-01',
    '2024-12-31',
    'IN',
    'ready',
    '{"total_employees": 120, "total_payroll": 2400000000, "average_salary": 20000000, "departments": {"Technology": 45, "Sales": 25, "Marketing": 20, "Operations": 15, "HR": 10, "Finance": 5}, "positions": {"Senior Developer": 30, "Team Lead": 15, "Sales Manager": 20, "Marketing Executive": 18}}',
    '{"BASIC": {"total": 1440000000, "average": 12000000, "count": 120, "name": "Basic Salary"}, "HRA": {"total": 576000000, "average": 4800000, "count": 120, "name": "House Rent Allowance"}, "PF_EMP": {"total": 172800000, "average": 1440000, "count": 120, "name": "Provident Fund (Employee)"}, "ESI_EMP": {"total": 36000000, "average": 300000, "count": 120, "name": "ESI (Employee)"}, "TDS": {"total": 240000000, "average": 2000000, "count": 120, "name": "Income Tax (TDS)"}, "NETPAY": {"total": 1951200000, "average": 16260000, "count": 120, "name": "Net Pay"}}',
    '{"previous_month_total": 2200000000, "variance": {"BASIC": 9.1, "HRA": 12.5, "PF_EMP": 8.3, "ESI_EMP": 6.7, "TDS": 25.8, "NETPAY": 11.4}, "trend": "increasing", "previous_month": {"BASIC": {"total": 1320000000, "average": 11000000}}}',
    '[{"type": "variance", "component": "TDS", "component_name": "Income Tax (TDS)", "variance": 25.8, "severity": "high", "message": "Income Tax (TDS) shows 25.8% increase from last month"}, {"type": "variance", "component": "HRA", "component_name": "House Rent Allowance", "variance": 12.5, "severity": "medium", "message": "House Rent Allowance shows 12.5% increase from last month"}, {"type": "variance", "component": "NETPAY", "component_name": "Net Pay", "variance": 11.4, "severity": "medium", "message": "Net Pay shows 11.4% increase from last month"}]',
    120,
    2400000000,
    20000000,
    9.1,
    120,
    2400000000,
    1,
    NOW(),
    NOW(),
    1,
    1
);

-- =================================================================
-- DEMO RECORD 4: INDONESIA - EXPORTED STATE
-- Shows: Completed workflow, historical data for comparison
-- =================================================================

INSERT INTO payroll_analytics (
    id,
    period_name,
    date_from,
    date_to,
    country,
    state,
    employee_metrics,
    salary_components,
    comparison_data,
    anomaly_alerts,
    total_employees,
    total_payroll,
    average_salary,
    variance_percentage,
    preview_record_count,
    preview_total_amount,
    currency_id,
    create_date,
    write_date,
    create_uid,
    write_uid
) VALUES (
    104,
    'November 2024 - Indonesia Demo',
    '2024-11-01',
    '2024-11-30',
    'ID',
    'exported',
    '{"total_employees": 78, "total_payroll": 1150000000, "average_salary": 14743590, "departments": {"Engineering": 32, "Sales": 18, "Marketing": 13, "HR": 8, "Finance": 7}, "positions": {"Software Engineer": 22, "Sales Executive": 13, "Marketing Specialist": 10}}',
    '{"BASIC": {"total": 780000000, "average": 10000000, "count": 78, "name": "Basic Salary"}, "BPJS_KES_EMP": {"total": 11700000, "average": 150000, "count": 78, "name": "BPJS Healthcare (Employee)"}, "BPJS_JHT_EMP": {"total": 15600000, "average": 200000, "count": 78, "name": "Old Age Fund (Employee)"}, "BPJS_JP_EMP": {"total": 7800000, "average": 100000, "count": 78, "name": "Pension (Employee)"}, "MONPIT": {"total": 115000000, "average": 1474359, "count": 78, "name": "Income Tax"}, "NETPAY": {"total": 999900000, "average": 12821795, "count": 78, "name": "Net Pay"}}',
    '{"previous_month_total": 1100000000, "variance": {"BASIC": 4.5, "BPJS_KES_EMP": 3.2, "BPJS_JHT_EMP": 2.8, "MONPIT": 6.4, "NETPAY": 4.1}, "trend": "stable", "previous_month": {"BASIC": {"total": 745000000, "average": 9550000}}}',
    '[]',
    78,
    1150000000,
    14743590,
    4.5,
    78,
    1150000000,
    1,
    NOW() - INTERVAL '1 month',
    NOW() - INTERVAL '10 days',
    1,
    1
);

-- =================================================================
-- DEMO RECORD 5: VIETNAM - DRAFT STATE
-- Shows: In-progress analytics, preliminary data
-- =================================================================

INSERT INTO payroll_analytics (
    id,
    period_name,
    date_from,
    date_to,
    country,
    state,
    employee_metrics,
    salary_components,
    comparison_data,
    anomaly_alerts,
    total_employees,
    total_payroll,
    average_salary,
    variance_percentage,
    preview_record_count,
    preview_total_amount,
    currency_id,
    create_date,
    write_date,
    create_uid,
    write_uid
) VALUES (
    105,
    'January 2025 - Vietnam Demo',
    '2025-01-01',
    '2025-01-31',
    'VN',
    'draft',
    '{"total_employees": 65, "total_payroll": 900000000, "average_salary": 13846154, "departments": {"Development": 30, "Operations": 20, "Support": 10, "Admin": 5}, "positions": {"Developer": 25, "Operations Manager": 15, "Support Specialist": 12}}',
    '{"BASIC": {"total": 650000000, "average": 10000000, "count": 65, "name": "Basic Salary"}, "ALLOWANCES": {"total": 97500000, "average": 1500000, "count": 65, "name": "Allowances"}, "SOCIAL_INS": {"total": 32500000, "average": 500000, "count": 65, "name": "Social Insurance"}, "PIT": {"total": 90000000, "average": 1384615, "count": 65, "name": "Personal Income Tax"}, "NETPAY": {"total": 780000000, "average": 12000000, "count": 65, "name": "Net Pay"}}',
    '{"previous_month_total": 850000000, "variance": {"BASIC": 5.9, "ALLOWANCES": 4.8, "SOCIAL_INS": 4.8, "PIT": 5.9, "NETPAY": 7.3}, "trend": "increasing", "previous_month": {"BASIC": {"total": 620000000, "average": 10000000}}}',
    '[{"type": "variance", "component": "NETPAY", "component_name": "Net Pay", "variance": 7.3, "severity": "low", "message": "Net Pay shows 7.3% increase from last month"}]',
    65,
    900000000,
    13846154,
    5.9,
    65,
    900000000,
    1,
    NOW(),
    NOW(),
    1,
    1
);

-- =================================================================
-- UPDATE SEQUENCE (if using PostgreSQL)
-- =================================================================
-- SELECT setval('payroll_analytics_id_seq', 105);

-- =================================================================
-- DEMO VERIFICATION QUERIES
-- =================================================================

-- Query 1: Show all demo records with key metrics
SELECT 
    period_name,
    country,
    state,
    total_employees,
    ROUND(total_payroll/1000000, 2) as total_payroll_millions,
    ROUND(average_salary/1000, 0) as avg_salary_thousands,
    variance_percentage,
    date_from,
    date_to
FROM payroll_analytics 
WHERE period_name LIKE '%Demo%'
ORDER BY country, date_from DESC;

-- Query 2: Show state distribution for demo
SELECT 
    state,
    COUNT(*) as record_count,
    SUM(total_employees) as total_employees,
    ROUND(SUM(total_payroll)/1000000, 2) as total_payroll_millions
FROM payroll_analytics 
WHERE period_name LIKE '%Demo%'
GROUP BY state
ORDER BY state;

-- Query 3: Show variance analysis summary
SELECT 
    period_name,
    country,
    state,
    variance_percentage,
    CASE 
        WHEN variance_percentage > 8 THEN 'High Growth'
        WHEN variance_percentage > 4 THEN 'Moderate Growth' 
        WHEN variance_percentage > 0 THEN 'Low Growth'
        ELSE 'Stable/Decline'
    END as growth_category
FROM payroll_analytics 
WHERE period_name LIKE '%Demo%'
ORDER BY variance_percentage DESC;

-- =================================================================
-- DEMO SCRIPT COMPLETE
-- 
-- This SQL creates 5 comprehensive demo records showcasing:
-- 1. Different approval states (draft, ready, approved, exported)
-- 2. Multiple countries (Indonesia, Vietnam, India)
-- 3. Various employee counts (62-120 employees)
-- 4. Different variance patterns (stable to high growth)
-- 5. Anomaly alerts (low to high severity)
-- 6. Complex salary component breakdowns
-- 7. Historical comparison data
-- 
-- Perfect for demonstrating all dashboard features!
-- =================================================================