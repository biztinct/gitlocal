#!/usr/bin/env python3
"""
Script to fix the analytics generation for July 2025 Vietnam payslips
Run this in Odoo shell or as a script
"""

def fix_july_2025_analytics():
    """Fix analytics for July 2025 Vietnam payslips"""
    
    # Delete the incorrect September 2025 record
    september_analytics = env['payroll.analytics'].search([
        ('period_name', 'like', 'September 2025'),
        ('country', '=', 'VN')
    ])
    if september_analytics:
        print(f"Deleting incorrect September analytics: {september_analytics.period_name}")
        september_analytics.unlink()
    
    # Find the July 2025 payslips that are in Level 2
    july_payslips = env['hr.payslip'].search([
        ('date_from', '>=', '2025-07-01'),
        ('date_to', '<=', '2025-07-31'), 
        ('state', '=', 'level2')
    ])
    
    print(f"Found {len(july_payslips)} July 2025 Level 2 payslips")
    
    if july_payslips:
        # Print some debug info
        print("Payslip details:")
        for slip in july_payslips[:5]:  # First 5
            print(f"  - {slip.employee_id.name}: {slip.date_from} to {slip.date_to}, State: {slip.state}")
        
        # Generate correct analytics for July 2025
        from datetime import date
        
        analytics_model = env['payroll.analytics']
        july_analytics = analytics_model.generate_analytics(
            country='VN',
            date_from=date(2025, 7, 1),
            date_to=date(2025, 7, 31)
        )
        
        print(f"Generated analytics: {july_analytics.period_name}")
        print(f"Total Employees: {july_analytics.total_employees}")
        print(f"Total Payroll: {july_analytics.total_payroll}")
        
        # Set the analytics to ready for approval state
        july_analytics.write({'state': 'ready'})
        
        print("✅ Analytics fixed successfully!")
        return july_analytics
    else:
        print("❌ No July 2025 Level 2 payslips found!")
        
        # Debug: Check what payslips exist
        all_payslips = env['hr.payslip'].search([
            ('date_from', '>=', '2025-07-01'),
            ('date_to', '<=', '2025-07-31')
        ])
        print(f"Found {len(all_payslips)} July payslips in total")
        for slip in all_payslips[:3]:
            print(f"  - {slip.employee_id.name}: State {slip.state}")
        
        return None

# Run the fix
if __name__ == '__main__':
    result = fix_july_2025_analytics()