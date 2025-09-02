-- =================================================================
-- INDONESIA AUGUST 2025 - ADDITIONAL DEMO RECORD
-- Shows: Seasonal variance, bonus payments, higher employee count
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
    106,
    'August 2025 - Indonesia Demo',
    '2025-08-01',
    '2025-08-31',
    'ID',
    'ready',
    '{"total_employees": 92, "total_payroll": 1580000000, "average_salary": 17173913, "departments": {"Engineering": 38, "Sales": 22, "Marketing": 16, "HR": 9, "Finance": 7}, "positions": {"Software Engineer": 28, "Senior Engineer": 10, "Sales Executive": 17, "Marketing Specialist": 14, "Sales Manager": 5}, "seasonal_notes": "Independence Day bonus included", "new_hires": 7, "resignations": 2}',
    '{"BASIC": {"total": 920000000, "average": 10000000, "count": 92, "name": "Basic Salary"}, "INDEPENDENCE_BONUS": {"total": 184000000, "average": 2000000, "count": 92, "name": "Independence Day Bonus"}, "TUNJANGAN_TRANSPORT": {"total": 46000000, "average": 500000, "count": 92, "name": "Transportation Allowance"}, "TUNJANGAN_MAKAN": {"total": 27600000, "average": 300000, "count": 92, "name": "Meal Allowance"}, "BPJS_KES_EMP": {"total": 13800000, "average": 150000, "count": 92, "name": "BPJS Healthcare (Employee)"}, "BPJS_JHT_EMP": {"total": 18400000, "average": 200000, "count": 92, "name": "Old Age Fund (Employee)"}, "BPJS_JP_EMP": {"total": 9200000, "average": 100000, "count": 92, "name": "Pension (Employee)"}, "UNION_DUES": {"total": 4600000, "average": 50000, "count": 92, "name": "Union Dues"}, "MONPIT": {"total": 142000000, "average": 1543478, "count": 92, "name": "Income Tax"}, "NETPAY": {"total": 1317400000, "average": 14319565, "count": 92, "name": "Net Pay"}}',
    '{"previous_month_total": 1320000000, "variance": {"BASIC": 18.5, "INDEPENDENCE_BONUS": 100.0, "TUNJANGAN_TRANSPORT": 7.2, "TUNJANGAN_MAKAN": 5.8, "BPJS_KES_EMP": 10.4, "BPJS_JHT_EMP": 15.6, "BPJS_JP_EMP": 12.2, "MONPIT": 23.5, "NETPAY": 19.7}, "trend": "increasing", "previous_month": {"BASIC": {"total": 776000000, "average": 9200000}, "total_employees": 84}, "seasonal_factors": ["Independence Day bonus payment", "New employee onboarding", "Mid-year salary adjustments"]}',
    '[{"type": "variance", "component": "INDEPENDENCE_BONUS", "component_name": "Independence Day Bonus", "variance": 100.0, "severity": "high", "message": "Independence Day Bonus is a seasonal payment - expected annual occurrence"}, {"type": "variance", "component": "MONPIT", "component_name": "Income Tax", "variance": 23.5, "severity": "high", "message": "Income Tax shows 23.5% increase due to bonus payments"}, {"type": "variance", "component": "NETPAY", "component_name": "Net Pay", "variance": 19.7, "severity": "medium", "message": "Net Pay shows 19.7% increase due to Independence Day bonus"}, {"type": "variance", "component": "BPJS_JHT_EMP", "component_name": "Old Age Fund (Employee)", "variance": 15.6, "severity": "medium", "message": "Old Age Fund (Employee) shows 15.6% increase from salary adjustments"}, {"type": "seasonal", "component": "OVERALL", "component_name": "Payroll Total", "variance": 19.7, "severity": "low", "message": "August payroll includes seasonal Independence Day bonus - normal annual pattern"}]',
    92,
    1580000000,
    17173913,
    19.7,
    92,
    1580000000,
    1,
    '2025-08-31 23:59:59',
    '2025-09-01 08:30:00',
    1,
    1
);

-- =================================================================
-- VERIFICATION QUERY FOR AUGUST RECORD
-- =================================================================

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
WHERE period_name = 'August 2025 - Indonesia Demo';

-- =================================================================
-- COMPARE WITH OTHER INDONESIA RECORDS
-- =================================================================

SELECT 
    period_name,
    total_employees,
    ROUND(total_payroll/1000000, 2) as payroll_millions,
    variance_percentage,
    state,
    EXTRACT(MONTH FROM date_from) as month,
    EXTRACT(YEAR FROM date_from) as year
FROM payroll_analytics 
WHERE country = 'ID' AND period_name LIKE '%Demo%'
ORDER BY date_from DESC;

-- =================================================================
-- AUGUST 2025 INDONESIA DEMO RECORD FEATURES:
--
-- 🎯 KEY HIGHLIGHTS:
-- • 92 employees (highest Indonesia count)
-- • Rp 1.58B total payroll (highest amount)
-- • 19.7% variance (seasonal bonus impact)
-- • 5 anomaly alerts (including seasonal explanation)
-- • Independence Day bonus component
-- • Complex allowance structure
--
-- 🏆 PERFECT FOR DEMO:
-- • Shows seasonal payroll variations
-- • Demonstrates bonus payment handling  
-- • Higher employee count (92 vs 85/78)
-- • Complex variance explanations
-- • Multiple alert types (variance + seasonal)
-- • Rich departmental breakdown
-- • Transportation & meal allowances
-- • Indonesian cultural context (Independence Day)
--
-- 🔍 DEMO SCENARIOS:
-- 1. Seasonal Variance Analysis
-- 2. Bonus Payment Impact
-- 3. Complex Alert Classification  
-- 4. Multi-month Comparison
-- 5. Cultural/Regional Considerations
-- =================================================================