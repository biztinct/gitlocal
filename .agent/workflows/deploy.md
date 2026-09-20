---
description: Deploy changed modules to Payobook19 server and restart Odoo
---

// turbo-all

# Deploy to Payobook19

This workflow syncs changed Odoo modules to the Payobook19 server and restarts the Odoo service.

**IMPORTANT:** After making ANY code changes to module files, ALWAYS deploy the changed modules and restart the server automatically. Do NOT ask the user — just do it.

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

### 2. Fix File Permissions
Rsync preserves local Mac file ownership (uid 502) which makes files unreadable by the `odoo` user. **Always** fix permissions after syncing:

```bash
ssh Payobook19 "sudo chown -R odoo:odoo /odoo/odoo-server/addons/<MODULE_NAME>/ && sudo chmod -R u+rX /odoo/odoo-server/addons/<MODULE_NAME>/"
```

### 3. Restart Odoo Server
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

## ⚠️ DO NOT DEPLOY — Incompatible Core Modules
The following modules in gitlocal are OLD Odoo 16/17 forks and must **NEVER** be deployed to the Odoo 19 server. Deploying them will overwrite the native Odoo 19 versions and crash the server.
- `account` — Old Odoo 16 fork, causes `ImportError: cannot import name 'WARNING_MESSAGE'`
- `hr_attendance_sheet` — Not installed, not compatible
- `hr_timesheet_sheet` — Not installed, not compatible
- `ohrms_overtime` — Not installed, not compatible
- `sa_attendance_late_minutes` — Not installed, not compatible
- `hr_attendance_modification_tracking` — Not installed, not compatible

## Example: Deploy Single Module
```bash
rsync -avz --delete --rsync-path="sudo rsync" /Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_vietnam/ Payobook19:/odoo/odoo-server/addons/pb_hr_payroll_vietnam/
ssh Payobook19 "sudo chown -R odoo:odoo /odoo/odoo-server/addons/pb_hr_payroll_vietnam/ && sudo chmod -R u+rX /odoo/odoo-server/addons/pb_hr_payroll_vietnam/ && sudo service odoo-server restart"
```

## Example: Deploy Multiple Modules
```bash
for module in pb_hr_payroll_formula pb_hr_payroll_vietnam; do
  rsync -avz --delete --rsync-path="sudo rsync" /Users/adity/Documents/GitHub/gitlocal/$module/ Payobook19:/odoo/odoo-server/addons/$module/
  ssh Payobook19 "sudo chown -R odoo:odoo /odoo/odoo-server/addons/$module/ && sudo chmod -R u+rX /odoo/odoo-server/addons/$module/"
done
ssh Payobook19 "sudo service odoo-server restart"
```
