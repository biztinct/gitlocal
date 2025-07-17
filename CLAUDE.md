# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an **Odoo 16 Community Edition** multi-country HR Payroll system with enhanced spreadsheet functionality. The codebase consists of 7 interconnected modules providing comprehensive payroll management for companies operating across multiple countries (primarily Asia-Pacific region).

## Development Memories

- Working now for Vietnam and India

## Development Commands

### Module Management
```bash
# Install/update modules during development
python -m odoo -c odoo.conf -d your_database -u om_hr_payroll,pb_hr_payroll_base,pb_hr_payroll_indonesia,pb_hr_payroll_india

# Install new modules
python -m odoo -c odoo.conf -d your_database -i module_name

# Start development server with auto-reload
python -m odoo -c odoo.conf -d your_database --dev=reload,qweb,werkzeug,xml
```

[... rest of the existing content remains unchanged ...]