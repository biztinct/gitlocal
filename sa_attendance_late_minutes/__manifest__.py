{
    "name":         "Attendance Late Minutes Calculation",
    "version":      "16.0",
    'summary':      "Attendance Late Minutes, Late Minutes, Late Employee, Employee Late, Late Deduction, Attendance Deduction, Late Arrival, Employee Late Minutes, Deduction Rules, lateness, employee lateness, late-minutes, Late Tracking, Attendance Rules, Employee Attendance, Deduction Policy, Attendance Tracking, Late Arrival Tracking, Employee Attendance Deduction, Attendance Late, Attendance Late Minutes, Employee Time Tracking, Late Arrival Deduction,  Time Deduction Policy, Late Arrival Fee, Employee Tardiness, Late Hours, Late Clock-in Deduction, Late Clock-in, Employee Tardiness Tracking, Deduct for Late Arrival, Track Employee Lateness, Late Check-ins, Late Check-in,  Late Entry Management, Attendance, Attendance Extension, Track Attendance Deductions, Employee Time Management",
    "description":  "This module adds a Late minutes computed field in hr.attendance and adds a capability to deduct from employee attendance based on customizable rules",
    'author':       "SOFT TECH LTD",
    "website":      "softatt.com",
    "license":      "OPL-1",
    "category":     "hr",
    "depends":      ["hr", "hr_attendance", "hr_contract"],
    "currency":     "USD",
    "data": [
        "security/ir.model.access.csv",
        "security/security.xml",
        
        "views/attendance_rule.xml",
        "views/res_conf.xml",
        "views/hr_attendance.xml",
        "views/hr_employee.xml",
    ],
    "images": ['static/description/banner.gif'],

}
