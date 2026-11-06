const WORKBOOK_ROWS = [
  {
    "code": "BASIC_SALARY",
    "name": "Basic contractual salary",
    "group": "earnings",
    "source": "Earning Codes!A5:H5",
    "original": {
      "C": "Fixed",
      "D": "Cash",
      "E": "Taxable",
      "F": "Included subject to eligibility/cap",
      "G": "Working-day proration",
      "H": "Monthly"
    }
  },
  {
    "code": "UNIFORM",
    "name": "Uniform allowance",
    "group": "earnings",
    "source": "Earning Codes!A6:H6",
    "original": {
      "C": "Occationally",
      "D": "Cash",
      "E": "Conditional exempt",
      "F": "Excluded",
      "G": "No",
      "H": "Ad hoc"
    }
  },
  {
    "code": "SEVERANCE_STAT",
    "name": "Statutory severance allowance",
    "group": "earnings",
    "source": "Earning Codes!A7:H7",
    "original": {
      "C": "Termination",
      "D": "Cash",
      "E": "Exempt within statutory entitlement",
      "F": "Excluded",
      "G": "No",
      "H": "Ad hoc"
    }
  },
  {
    "code": "OTHER_EXEMPT",
    "name": "Other exempt reimbursement",
    "group": "earnings",
    "source": "Earning Codes!A8:H8",
    "original": {
      "C": "Reimbursement",
      "D": "Cash",
      "E": "Conditional exempt",
      "F": "Excluded",
      "G": "No",
      "H": "Ad hoc"
    }
  },
  {
    "code": "AL_ENCASH_EXEMPT",
    "name": "Unused annual-leave encashment",
    "group": "earnings",
    "source": "Earning Codes!A9:H9",
    "original": {
      "C": "Termination",
      "D": "Cash",
      "E": "Exempt for qualifying payment",
      "F": "Excluded",
      "G": "No",
      "H": "Ad hoc"
    }
  },
  {
    "code": "TRANSPORT_ADD",
    "name": "Additional transportation",
    "group": "earnings",
    "source": "Earning Codes!A10:H10",
    "original": {
      "C": "Allowance",
      "D": "Cash",
      "E": "Taxable unless reimbursement evidence",
      "F": "Excluded",
      "G": "Policy dependent",
      "H": "Monthly/Ad hoc"
    }
  },
  {
    "code": "TRANSPORT",
    "name": "Transportation allowance",
    "group": "earnings",
    "source": "Earning Codes!A11:H11",
    "original": {
      "C": "Allowance",
      "D": "Cash",
      "E": "Taxable",
      "F": "Excluded",
      "G": "Working-day proration",
      "H": "Monthly"
    }
  },
  {
    "code": "PHONE_ALLOW",
    "name": "Phone allowance",
    "group": "earnings",
    "source": "Earning Codes!A12:H12",
    "original": {
      "C": "Allowance",
      "D": "Cash",
      "E": "Taxable",
      "F": "Excluded",
      "G": "Working-day proration",
      "H": "Monthly"
    }
  },
  {
    "code": "PRIVATE_INS_ALLOW",
    "name": "Private insurance allowance for expat",
    "group": "earnings",
    "source": "Earning Codes!A13:H13",
    "original": {
      "C": "Benefit/Allowance",
      "D": "Cash",
      "E": "Taxable",
      "F": "Confirm",
      "G": "No",
      "H": "Monthly/Ad hoc"
    }
  },
  {
    "code": "PREMIUM_INS_ALLOW",
    "name": "Premium Health Insurance for family member",
    "group": "earnings",
    "source": "Earning Codes!A14:H14",
    "original": {
      "C": "Benefit/Allowance",
      "D": "Non-cash",
      "E": "Taxable",
      "F": "Excluded",
      "G": "No",
      "H": "Scheme"
    }
  },
  {
    "code": "LOGISTICS_INC",
    "name": "Logistics Incentive",
    "group": "earnings",
    "source": "Earning Codes!A15:H15",
    "original": {
      "C": "Incentive",
      "D": "Cash",
      "E": "Taxable",
      "F": "Excluded",
      "G": "No",
      "H": "Monthly/Ad hoc"
    }
  },
  {
    "code": "AGS_INC",
    "name": "Season Agronomy Incentive",
    "group": "earnings",
    "source": "Earning Codes!A16:H16",
    "original": {
      "C": "Incentive",
      "D": "Cash",
      "E": "Taxable",
      "F": "Excluded",
      "G": "No",
      "H": "Scheme"
    }
  },
  {
    "code": "PRODUCT_LAUNCH_INC",
    "name": "New product launch incentive",
    "group": "earnings",
    "source": "Earning Codes!A17:H17",
    "original": {
      "C": "Incentive",
      "D": "Cash",
      "E": "Taxable",
      "F": "Excluded",
      "G": "No",
      "H": "Ad hoc"
    }
  },
  {
    "code": "VARIABLE_BONUS",
    "name": "Variable Bonus",
    "group": "earnings",
    "source": "Earning Codes!A18:H18",
    "original": {
      "C": "Bonus",
      "D": "Cash",
      "E": "Taxable",
      "F": "Excluded",
      "G": "No",
      "H": "Scheme"
    }
  },
  {
    "code": "REFERRAL_INC",
    "name": "Referral Incentive",
    "group": "earnings",
    "source": "Earning Codes!A19:H19",
    "original": {
      "C": "Incentive",
      "D": "Cash",
      "E": "Taxable",
      "F": "Excluded",
      "G": "No",
      "H": "Ad hoc"
    }
  },
  {
    "code": "OTHER_TAXABLE",
    "name": "Other taxable allowance",
    "group": "earnings",
    "source": "Earning Codes!A20:H20",
    "original": {
      "C": "Allowance",
      "D": "Cash",
      "E": "Taxable",
      "F": "Excluded",
      "G": "Policy dependent",
      "H": "Ad hoc"
    }
  },
  {
    "code": "ADJ_ADD",
    "name": "Prior-period addition",
    "group": "earnings",
    "source": "Earning Codes!A21:H21",
    "original": {
      "C": "Adjustment",
      "D": "Cash",
      "E": "Depends on source component",
      "F": "Excluded",
      "G": "No",
      "H": "Ad hoc"
    }
  },
  {
    "code": "ADJ_DEDUCT",
    "name": "Prior-period deduction adjustment",
    "group": "earnings",
    "source": "Earning Codes!A22:H22",
    "original": {
      "C": "Adjustment",
      "D": "Cash",
      "E": "Depends on source component",
      "F": "Excluded",
      "G": "No",
      "H": "Ad hoc"
    }
  },
  {
    "code": "NONCASH_BENEFIT",
    "name": "Taxable non-cash benefit",
    "group": "earnings",
    "source": "Earning Codes!A23:H23",
    "original": {
      "C": "Benefit",
      "D": "Non-cash",
      "E": "Taxable",
      "F": "Excluded",
      "G": "No",
      "H": "Monthly/Ad hoc"
    }
  },
  {
    "code": "OT_WEEKDAY",
    "name": "Weekday overtime pay",
    "group": "earnings",
    "source": "Earning Codes!A24:H24",
    "original": {
      "C": "Overtime",
      "D": "Cash",
      "E": "PIT exempt for qualifying OT",
      "F": "Excluded",
      "G": "Hours × rate",
      "H": "Monthly"
    }
  },
  {
    "code": "OT_WEEKEND",
    "name": "Weekend overtime pay",
    "group": "earnings",
    "source": "Earning Codes!A25:H25",
    "original": {
      "C": "Overtime",
      "D": "Cash",
      "E": "PIT exempt for qualifying OT",
      "F": "Excluded",
      "G": "Hours × 200%",
      "H": "Monthly"
    }
  },
  {
    "code": "OT_HOLIDAY",
    "name": "Public-holiday overtime pay",
    "group": "earnings",
    "source": "Earning Codes!A26:H26",
    "original": {
      "C": "Overtime",
      "D": "Cash",
      "E": "PIT exempt for qualifying OT",
      "F": "Excluded",
      "G": "Hours × approved rate",
      "H": "Monthly"
    }
  },
  {
    "code": "NIGHT_SHIFT",
    "name": "Night-work premium",
    "group": "earnings",
    "source": "Earning Codes!A27:H27",
    "original": {
      "C": "Overtime",
      "D": "Cash",
      "E": "PIT exempt for qualifying payment",
      "F": "Excluded",
      "G": "Hours × approved rate",
      "H": "Monthly"
    }
  },
  {
    "code": "THIRTEENTH_MONTH",
    "name": "13th-month salary",
    "group": "earnings",
    "source": "Earning Codes!A28:H28",
    "original": {
      "C": "Bonus",
      "D": "Cash",
      "E": "Taxable",
      "F": "Excluded",
      "G": "Policy proration",
      "H": "Annual"
    }
  },
  {
    "code": "EE_SI",
    "name": "Employee Social Insurance",
    "group": "deductions",
    "source": "Deduction Codes!A4:F4",
    "original": {
      "C": "Statutory",
      "D": "Employee",
      "E": "Eligible insurance salary × 8%, capped",
      "F": "Yes"
    }
  },
  {
    "code": "EE_HI",
    "name": "Employee Health Insurance",
    "group": "deductions",
    "source": "Deduction Codes!A5:F5",
    "original": {
      "C": "Statutory",
      "D": "Employee",
      "E": "Eligible insurance salary × 1.5%, capped",
      "F": "Yes"
    }
  },
  {
    "code": "EE_UI",
    "name": "Employee Unemployment Insurance",
    "group": "deductions",
    "source": "Deduction Codes!A6:F6",
    "original": {
      "C": "Statutory",
      "D": "Employee",
      "E": "Eligible local salary × 1%, UI cap",
      "F": "Yes"
    }
  },
  {
    "code": "UNION_DUES",
    "name": "Employee Union Dues",
    "group": "deductions",
    "source": "Deduction Codes!A7:F7",
    "original": {
      "C": "Union",
      "D": "Employee",
      "E": "Eligible insurance salary × 0.5% (company-applied), capped at 253,000",
      "F": "No"
    }
  },
  {
    "code": "PIT",
    "name": "Personal Income Tax",
    "group": "deductions",
    "source": "Deduction Codes!A8:F8",
    "original": {
      "C": "Statutory",
      "D": "Employee",
      "E": "Progressive / flat 10% / non-resident 20%",
      "F": "N/A"
    }
  },
  {
    "code": "ADVANCE",
    "name": "Salary Advance",
    "group": "deductions",
    "source": "Deduction Codes!A9:F9",
    "original": {
      "C": "Company",
      "D": "Employee",
      "E": "Approved amount",
      "F": "No"
    }
  },
  {
    "code": "PRIOR_DED",
    "name": "Prior-period Deduction",
    "group": "deductions",
    "source": "Deduction Codes!A10:F10",
    "original": {
      "C": "Adjustment",
      "D": "Employee",
      "E": "Approved amount",
      "F": "Depends on source"
    }
  },
  {
    "code": "OTHER_DED",
    "name": "Other Deduction",
    "group": "deductions",
    "source": "Deduction Codes!A11:F11",
    "original": {
      "C": "Company",
      "D": "Employee",
      "E": "Approved/legal amount",
      "F": "No"
    }
  },
  {
    "code": "VN_SHUI_LOCAL",
    "name": "Vietnam SI/HI/UI",
    "group": "benefits",
    "source": "Benefits!A4:F4",
    "original": {
      "C": "Mandatory",
      "D": "Eligible local employees",
      "E": "10.5% of capped bases",
      "F": "21.5% of capped bases"
    }
  },
  {
    "code": "VN_SI_HI_FOREIGN",
    "name": "Foreign employee SI/HI",
    "group": "benefits",
    "source": "Benefits!A5:F5",
    "original": {
      "C": "Mandatory when eligible",
      "D": "Eligible foreign employees with qualifying permit/contract",
      "E": "9.5% of capped SI/HI base",
      "F": "20.5% of capped SI/HI base"
    }
  },
  {
    "code": "PRIVATE_HEALTH_EMP",
    "name": "Private health insurance - employee",
    "group": "benefits",
    "source": "Benefits!A6:F6",
    "original": {
      "C": "Voluntary/company",
      "D": "TBD",
      "E": "TBD",
      "F": "TBD"
    }
  },
  {
    "code": "PRIVATE_HEALTH_DEP",
    "name": "Private health insurance - dependants",
    "group": "benefits",
    "source": "Benefits!A7:F7",
    "original": {
      "C": "Voluntary/company",
      "D": "TBD",
      "E": "TBD",
      "F": "TBD"
    }
  },
  {
    "code": "UNION_MEMBER",
    "name": "Union membership",
    "group": "benefits",
    "source": "Benefits!A8:F8",
    "original": {
      "C": "Employee choice / organizational",
      "D": "Approved union members",
      "E": "Current payroll 0.5% capped",
      "F": "Employer 2%"
    }
  },
  {
    "code": "OTHER_BENEFITS",
    "name": "Other company benefits",
    "group": "benefits",
    "source": "Benefits!A9:F9",
    "original": {
      "C": "TBD",
      "D": "TBD",
      "E": "TBD",
      "F": "TBD"
    }
  }
];
