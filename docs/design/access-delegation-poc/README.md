# Access and Delegation design review

Open `../access-delegation-poc.html` in a browser. It is a standalone document
with three interactive concepts, a review of the current product, first-party
research links, a comparison and a recommendation. No external dependencies
or production API calls are used.

- **01 Access Studio (recommended):** role library, per-action record scopes,
  record conditions, field controls with a live form preview, delegation and
  local revision history.
- **02 Guided Setup:** template, record scope, fields and review; individual
  actions and rules remain available through focused editors.
- **03 People Passport:** effective-access explanation, multiple grant sources,
  source-role editing and temporary access visibility.

All data is fictional. Concept state is independent and held in memory; reload
resets it. A chosen design preference is stored locally when storage is
available and can be downloaded as a text file. It does not constitute approval
to implement or change live permissions.

The demo models company boundaries, self/direct-report record ownership,
department/status AND/OR conditions, field visibility/editability and separate
input-on-create settings. The simulator tests employee View/Edit/Delete. It
does not reproduce the complete Odoo authorization engine. Unsupported models,
real user management, backend persistence, notification, exact-time expiry,
masking and live enforcement are outside this design artifact.

## Scope and deployment

Only the static design-review environment is in scope:
`https://payobook.com/preview/access-delegation/`, served by nginx on
`Payobook19v2`. The deployment publishes the latest committed combined state
of the complete preview and its route, preserves existing server configuration,
backs up previous preview files, validates nginx and reloads it. It does not
deploy Odoo source or change databases, roles or permissions. Therefore no
module upgrade or migration is in scope for `payobook`, `payobook_template`,
`p0clone` or `rize`. Retired ABM is untouched.

After committing both the HTML and hosting files:

```sh
python3 docs/design/access-delegation-poc/deploy.py
```

The script rejects uncommitted preview bytes. Re-check the branch and worktree
immediately before running it. Exclude concurrent-session work from commits.
Chrome checks and deployment evidence are recorded in `verification.md` after
testing. Screenshots are viewed in memory; no test PNGs should be retained.
