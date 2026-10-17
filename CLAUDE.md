# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🚨 Deploy contract — ONE addons directory

**Every module deploys to `/odoo/odoo-server/addons` on the live server. Every
module, custom ones included. There is no second addons directory.**

`addons_path` in `/etc/odoo-server.conf` is now a single entry. `/odoo/custom/addons`
used to be a second entry and is gone: the name is occupied by a regular *file*
so `mkdir -p` and `rsync` into it fail loudly. Never recreate it. If a second
directory is ever genuinely needed, it must be added to `addons_path` in the
same change — never one without the other.

Why this is a rule and not a preference: the first `addons_path` entry WINS.
A module present in two paths loads from the first and the other copy is
ignored silently — no error, no log line. On 2026-08-26 that hid 31 versions of
`pb_formula_studio` (the entire Mapping/Journey programme) from all four
databases. The screens simply showed old behaviour.

### Deploying (the whole checklist — files on disk are only half of it)

1. **Clean the staging directory first**: `sudo rm -rf /tmp/deployX && mkdir -p /tmp/deployX`.
   A reused staging dir carries a previous deploy's modules into this one.
2. `rsync -az --exclude=__pycache__ --exclude='*.pyc' <modules> server:/tmp/deployX/`
3. **Per module** on the server:
   `sudo rsync -a --delete /tmp/deployX/<m>/ /odoo/odoo-server/addons/<m>/`
   Scoped to one module the `--delete` is correct — it clears files deleted
   upstream. **NEVER** use `--delete` with `/odoo/odoo-server/addons/` itself as
   the destination: that deletes every other module on the box.
4. **Never deploy this repo's copies of standard Odoo addons.** `web`, `hr`,
   `crm`, `website`, `resource`, `spreadsheet`, `hr_*`, `website_*` are vendored
   here as *older* snapshots than the server's. The server's copies come from
   its own odoo git clone. Split them with:
   `git -C /odoo/odoo-server ls-files addons | cut -d/ -f2 | sort -u` — that is
   the standard set; everything else is ours.
5. **Upgrade every database**, not just one: `payobook`, `abm`, `acme`,
   `payobook_template` drift apart independently. New files with an old
   `ir_module_module.latest_version` means none of that module's views, data or
   assets have loaded.
6. After JS/SCSS changes: `DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'`
   per database, then restart.

### Verifying (do not skip — this is how the silent failure was found)

- **Content**: hash each module tree on both sides, skipping `__pycache__`,
  `*.pyc` and `.DS_Store` (the repo has `.DS_Store` files the server won't).
  Every custom module must be byte-identical.
- **Version**: compare each manifest version to `ir_module_module.latest_version`
  in every database. Odoo prefixes the series, so DB `19.0.1.7.0` matches a
  manifest of `1.7.0` *or* `19.0.1.7.0` — normalise before comparing or ~30
  standard addons show up as false positives.

## Project Overview

This is an **Odoo 16 Community Edition** HR Payroll system with enhanced spreadsheet functionality. 

## Current Architecture (Post-Refactoring)

### 🏗️ **Module Structure**
```
📦 Multi-Country Payroll System
├── 🏛️ om_hr_payroll (Original base)
├── 🌏 pb_hr_payroll_base (Enhanced base framework)
├── 🇻🇳 pb_hr_payroll_vietnam
├── 🇮🇩 pb_hr_payroll_indonesia  
├── 🇮🇳 pb_hr_payroll_india
├── 🇸🇬 pb_hr_payroll_singapore
├── 🇹🇭 pb_hr_payroll_thailand
├── 🇰🇭 pb_hr_payroll_cambodia
├── 🇲🇾 pb_hr_payroll_malaysia
└── 📊 payroll_analytics_approval (Optional)
```


### 🔐 **Security Groups (Base Module)**
```python
# pb_hr_payroll_base security groups
- group_payroll_base_user
- group_payroll_base_officer  
- group_payroll_base_manager
- group_payroll_super_admin
- group_payroll_vietnam
- group_payroll_indonesia
- group_payroll_india
- group_payroll_singapore
- group_payroll_thailand
- group_payroll_cambodia
- group_payroll_malaysia
- group_payroll_analytics_user
- group_payroll_analytics_manager
- group_payroll_integration_user
```

### 🎨 **Design Principles Applied**
4. **Professional UI**: Consistent animations and styling across all dashboards
5. **Modular Architecture**: Base module handles shared functionality, country modules add specifics

### 📂 **Key Files and Their Purposes**

#### Base Module (pb_hr_payroll_base)
```
📁 pb_hr_payroll_base/
├── 🎯 views/payroll_menu_base.xml (Main menu structure)
├── 📋 views/payroll_setup_guide.xml (Universal setup guide)
├── 🔗 views/zoho_menu_integration.xml (Zoho integration menus)
├── 🏛️ models/payroll_dashboard_base.py (Core dashboard logic)
├── 🔐 security/payroll_base_security_enhanced.xml (All security groups)
└── 🎨 static/src/ (Shared CSS/JS assets)
```

#### Country Modules Pattern
```
📁 pb_hr_payroll_[country]/
├── 🎯 views/payroll_menu_structure.xml (Country-specific menus)
├── 📊 views/payroll_dashboard.xml (Country dashboard design)
├── 💰 data/hr_salary_rule_data.xml (Country tax rules)
├── 🏗️ data/hr_payroll_structure_data.xml (Payroll structures)
└── 🧙 wizards/ (Country-specific tools like SSF, CPF, etc.)
```

### 🚀 **Installation Order**
```bash
# 1. Install base modules first
pb_hr_payroll_base

# 2. Install country modules (any order)
pb_hr_payroll_vietnam
pb_hr_payroll_india  
pb_hr_payroll_indonesia
pb_hr_payroll_singapore
pb_hr_payroll_thailand
pb_hr_payroll_cambodia
pb_hr_payroll_malaysia

# 3. Optionally install analytics
payroll_analytics_approval
```

