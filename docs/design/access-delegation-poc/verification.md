# Revision 3 verification — 27 October 2026 (Australia/Sydney)

Implementation commits: `27f2ece52` and `3c411cad8`.
The final documentation commit records the verified results below.

## Expanded design

Option 1 now includes module-filtered People & assignments and Requests &
reviews, effective-access side panels, bulk assignment review, policy impact
and independent approval, profile maintenance, business actions, masking and
reasoned reveal, periodic reviews, lifecycle event previews and version restore.
Screens remains directly accessible. Record rules and form fields are nested
under Roles & permissions. Options 2 and 3 retain their independent examples.

## Validation

**54 assertions passed in Chrome against the deployed preview.** They cover:

- Module-filtered people, required assignment reason and reviewed bulk updates.
- Published access remaining unchanged by draft widening; company boundaries;
  affected-member impact; independent approval and required decision reasons.
- Approved policy becoming effective; restore-as-draft and a newly published
  narrower revision.
- Independent temporary access surviving profile-removal simulation and actual
  periodic profile removal.
- Assigned-profile retirement blocked; cloning with zero members; profile
  comparison; unassigned retirement; retired profiles excluded from assignment.
- Profile-package before/after review and approved shared-reference changes.
- Join event attribution, transfer removal of automatic profiles, and leaver
  suspension blocking independent grants too.
- Hiring owner blocked outside its module; separate payroll preparation and
  approval grants detected as a conflict; rejection and module-scoped queues.
- Explicit business-action grants, locked workflow stages, masked field
  rendering, reason-required reveal and its audit receipt.
- Preserved Screens, selected-person preview and source-role selection.
- Required revocation reason; extra-grant removal preserving the profile.
- New package requests opening the Requests subtab; automatic-assignment
  disclosure staying open; profile owner updates visible.
- Phone-width People, explanation drawer, Requests and Screens; Escape closing
  the drawer; Option 2 menu preview and Option 3 effective-access flows and
  their mobile layouts.

Desktop and 390 × 844 layouts were visually inspected. All tested mobile
views had no page-wide horizontal overflow. Temporary viewport override was
reset. The warning/error log was empty. Reload reset all fictional changes
before handoff. No design preference was selected by the test.

Testing found and fixed two interaction issues: submitting a package request
could retain the Reviews subtab, and toggling automatic assignment collapsed
its disclosure. Both corrections were verified on the deployed revision.

JavaScript and Python syntax, inline bundle consistency and git whitespace
checks passed. Nginx configuration validation and reload passed. Public HTML
is compared byte-for-byte with the repository artifact after final deployment.

## Deployment and cleanup

Only the isolated static design preview is in scope:
**https://payobook.com/preview/access-delegation/** on `Payobook19v2`.
File: `/var/www/payobook-previews/access-delegation/index.html`.

The deployer publishes the complete committed preview from the latest combined
branch state and rejects uncommitted source or a stale inline bundle. Existing
site configuration and concurrent commits are preserved. No Odoo code, database
permissions or module upgrades are involved for `payobook`,
`payobook_template`, `p0clone` or `rize`. Retired ABM is untouched.

Screenshots were inspected in memory. No test screenshot or PNG files were
written. The task-owned loopback server is stopped after final verification.
Unrelated `outputs/komal-learning-2026-10-23/` content is excluded and preserved.

---

# Revision 2 verification — 27 October 2026 (Australia/Sydney)

Implementation commit: `086768ce98089a9c9b9f072e8ceff2992a97be69`.
The follow-up records this evidence and clarifies the comparison-table wording.

## Review and design

- Re-read the existing Screens template, including menu map, “See it as”,
  visible/locked/hidden states, audience, role gates, orphan warnings and
  keyboard/drag ordering. Inspected Hiring sidebar definitions and resource
  models. Existing role and delegation review evidence remains below.
- Consulted first-party Zoho profile/module permissions, Microsoft security
  role editor, and Salesforce object access documentation. The HTML links the
  sources and distinguishes documented patterns from proposed navigation.
- All three options include module context, meaningful access profiles and
  Screens. Account types are separated from profiles. Profiles reference the
  current role definitions without duplicating policy controls.
- No production access changes or notifications were made.

## Deployed Chrome validation

**36 checks passed against the hosted preview:**

1. Global directory groups modules; local/global routes preserve a role edit.
2. Review names affected profiles, requires a reason, and updates source-role
   revision references in profiles.
3. Hiring owner cannot edit People through shared-role navigation; no People
   policy controls are rendered. Shared role package checkbox is disabled.
4. Profile review lists added references and applies the four-role package.
5. Shared directory role opens People in the profile menu; Recruiter alone
   leaves People hidden.
6. Actual-menu mode removes a hidden Candidates tile; hiding that tile leaves
   candidate View permission unchanged. Submenu reorder updates the map.
7. Hidden salary field removes the form input; hidden required name blocks
   role publication.
8. AND/OR conditions filter the sample records within the mandatory company.
9. Delegation requires a reason, remains pending approval, and a Hiring
   request does not appear in Payroll.
10. Guided review uses the profile's combined menu; assignment changes the
    selected person's preview. External account type blocks assignment of
    the administrative profile.
11. Passport denies outside-team access until an additional source grants it;
    Company B remains blocked. Source-role editor opens from the profile.
    Jordan's menu reflects the shared directory role in his own profile.
12. All three concepts fit a 390 × 844 viewport without page-wide horizontal
    overflow. Desktop and phone Screens layouts were inspected visually.
13. Preference enables a local download, persists on reload and clears.

Checks above group related assertions; the browser test log contained exactly
36 successful assertions. Chrome warning/error log was empty. The viewport
was reset, the test preference cleared, and demo state reset by reload.
No screenshot or PNG files were written; screenshots were viewed in memory.

JavaScript syntax, Python syntax, bundled-source consistency and git whitespace
checks passed. The deployer validates committed preview sources, hosting files
and the exact inline JavaScript bundle before uploading. Nginx configuration
test and reload passed. Public HTML is checked byte-for-byte against the local
artifact after the final deployment.

## Deployment boundary

Target: **https://payobook.com/preview/access-delegation/** on `Payobook19v2`.
File: `/var/www/payobook-previews/access-delegation/index.html`.
The complete current committed preview is deployed from the latest combined
branch state. Concurrent commits and unrelated
`outputs/komal-learning-2026-10-23/` content are preserved.

This is the isolated static design-review environment. No Odoo source, module
upgrade, database permission or migration is in scope for `payobook`,
`payobook_template`, `p0clone` or `rize`. Retired ABM remains untouched.

---

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
