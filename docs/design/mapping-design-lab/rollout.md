# Private design-review rollout — 16 October 2026

This rollout publishes the requested proof of concept for approval. It does **not** implement a chosen direction in the live payroll application.

## Provenance and target

- Repository implementation commit: `f10ec2e448ad9c8d2d076dc99c4b7c86f4a129b0`.
- Private review URL: https://payobook-mapping-design-lab.groovy-pixie-4012.chatgpt.site
- Sites project: `appgprj_6ad1b2d84d888191b2ac3be354913d0d`.
- Published version: **1**.
- Sites source commit: `2f4db4c70828bb479ecf9e01d3d1f591e82fbd7b`.
- Deployment: `appgdep_6ad1b65001d08191ab31ff24d3a46b75`; terminal status **succeeded**.
- Published HTML SHA-256: `8cd15a23dd952297c01b9aebeaded5ea4b7d402ffab9b5fc05594ed8be0bf433`.

The current branch and worktree were rechecked before publication. The complete prototype source and manifest were packaged from the pushed Sites source commit. The hosted HTML matches the repository artifact byte for byte. Unrelated workbook deletions and the untracked Singapore directory were preserved and excluded from commits.

The only environment in scope is this isolated private static review site. No Odoo module, database, job, or mail setting changed. No production deployment or database migration is needed for a design artifact.

## Validation

- JavaScript syntax and Git whitespace checks passed.
- **52 behavior/invariant checks** passed using jsdom and the actual HTML event handlers. Coverage included cancel/no blank writes, unique codes, leading-zero identifiers, amount/type validation, non-money net-pay role rejection, compatible destinations, source conflict preview/cancel, transform preview and division by zero, suggestions, search/recovery, all three designs, advanced-tool reachability, templates, and Undo.
- Chrome verified local layouts and the **published version**.
- Published Connection desk: text component creation reused the existing component; attempting to store a word as an amount was blocked; Undo restored the original; a new amount component showed `250,000 ₫` and the missing-source state; working days changed from currency to `22 days`; accepting the Department suggestion updated the review count.
- Published Focused journey: one component route, calculated-component explanation, and the grouped three-part whole Journey worked.
- Published Guided review: before/after preview preceded application, and the Nationality task resolved to contract text storage.
- Local layouts A/B/C and published Guided review were checked at **390 × 844**. There was no page-wide horizontal overflow. The temporary viewport override was reset.
- Chrome error log was empty after published checks.
- The demo was reset and left on Start here for the user. No preferred direction was selected on the user's behalf.
- No screenshot or PNG files were written locally during testing; task-owned prototype and publication directories contain **zero PNG files**. Pre-existing product assets and user images were untouched.

## Approval boundary

Recommendation: **A as the daily workspace**, with B's focused route explanation in detail and C's guided decisions inside review. The user can approve A, B, C, or a specific combination. A preference marked in the prototype is browser-local and does not constitute implementation approval.
