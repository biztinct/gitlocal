# Verification — 27 October 2026 (Australia/Sydney)

Implementation began with commit `c44eff8a55babaa60545ed2c3e107a594cde7029`.
The final follow-up corrects the guided scope preset: no uniform scope is
shown as selected until the administrator explicitly chooses one. Template
scopes remain individually visible in the advanced editor and review.

## Review evidence

- Read the existing Access UI templates, ability/profile models, role editor,
  assignment handling and delegation code.
- Inspected the live Payobook role list and New role composer in Chrome.
  Closed the unsaved composer and restored the original People view.
- Researched first-party Salesforce, Microsoft Dataverse, Zoho CRM, Okta and
  Odoo documentation. Source links and their design implications are embedded
  in the HTML. The three concepts are original proposed layouts.

## Validation

- JavaScript syntax and deployment-script Python syntax passed.
- Git whitespace validation passed.
- Local Chrome checks covered the three layouts; separate View/Edit scopes;
  read-only form preview; cross-company denial; AND/OR filtering; guided
  field preview; before/after review; required reason; independent grants;
  sensitive-field denial; and delegation reason/end-time validation.
- **24 deployed Chrome checks passed:** action dependencies; required-field
  protection and input visibility; rule filtering; company boundaries;
  revision history; payroll preparation/approval conflicts; account-profile
  compatibility; guided fine-tuning and field preview; delegation bounds,
  required reason and pending request; inherited access, salary protection
  and removal of the independent grant; all three layouts at 390 × 844;
  preference selection, download availability, persistence and clearing.
- No page-wide horizontal overflow at 390 px. Desktop and mobile layouts
  were visually inspected. Temporary viewport override was reset.
- Chrome warning/error log was empty. Test preference was cleared and all
  in-memory prototype changes reset before handoff.
- One initial assertion against an email-named select value encountered
  browser-tool redaction. Its visible selected option was checked instead;
  the control correctly displayed View. This was not an application failure.

## Deployment scope

Target: **https://payobook.com/preview/access-delegation/** on `Payobook19v2`.
Static file: `/var/www/payobook-previews/access-delegation/index.html`.
Route: `/etc/nginx/snippets/access-delegation-preview.conf`.

The deployment script publishes the entire current committed preview and
route, rejects uncommitted artifact bytes, retains backups, validates nginx
and reloads it. The existing site configuration is preserved. Public HTTP
content is compared byte-for-byte with the repository HTML. Existing homepage
and payroll-template preview returned HTTP 200 after deployment.

Only the static review artifact is in scope. No Odoo modules or database
permissions changed; `payobook`, `payobook_template`, `p0clone` and `rize`
require no module upgrade for this artifact. Retired ABM is untouched.

Concurrent branch commits were preserved. The unrelated untracked
`outputs/komal-learning-2026-10-23/` directory was excluded from commits.
No PNG or screenshot files were written by this test run: screenshots were
inspected in memory, and pre-existing images were left untouched.
