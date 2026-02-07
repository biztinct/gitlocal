---
description: Deploy changed modules to Payobook19 server and restart Odoo
---

# Deploy to Payobook19

This workflow syncs changed Odoo modules to the Payobook19 server and restarts the Odoo service.

## Server Details
- **Hostname:** Payobook19
- **Modules Path:** /odoo/odoo-server/addons/
- **Restart Command:** sudo service odoo-server restart

## Steps

### 1. Sync Module(s) to Server
For each changed module, run rsync to copy it to the server:

```bash
rsync -avz --delete --rsync-path="sudo rsync" /Users/adity/Documents/GitHub/gitlocal/<MODULE_NAME>/ Payobook19:/odoo/odoo-server/addons/<MODULE_NAME>/
```

// turbo
### 2. Restart Odoo Server
After syncing all modules, restart the Odoo service:

```bash
ssh Payobook19 "sudo service odoo-server restart"
```

## Common Module Names
- `pb_hr_payroll_formula`
- `pb_hr_payroll_base`
- `pb_hr_payroll_vietnam`
- `pb_hr_payroll_analytics`
- `payroll_analytics_approval`
- `om_hr_payroll`
- `pb_hr_flow`
- `pb_hr_govt`
- `hr_contract`

## Example: Deploy Single Module
```bash
rsync -avz --delete --rsync-path="sudo rsync" /Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_vietnam/ Payobook19:/odoo/odoo-server/addons/pb_hr_payroll_vietnam/
ssh Payobook19 "sudo service odoo-server restart"
```

## Example: Deploy Multiple Modules
```bash
for module in pb_hr_payroll_formula pb_hr_payroll_vietnam; do
  rsync -avz --delete --rsync-path="sudo rsync" /Users/adity/Documents/GitHub/gitlocal/$module/ Payobook19:/odoo/odoo-server/addons/$module/
done
ssh Payobook19 "sudo service odoo-server restart"
```

