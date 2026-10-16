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

## Revision 2 — source priority, holistic Journey, and transformation creation

The user selected the recommendation and requested another HTML review before implementation, specifically covering priority tags, the holistic Journey, transformation creation, and useful capabilities omitted from the initial POC.

- Implementation commit: `0460aa447313baebe68daa9c860c521e22f37e8f`.
- Published at the same private review URL, version **2**.
- Sites source commit: `416e18ccca742df30b93f318dcad70e002328a80`.
- Deployment: `appgdep_6ad1c95693448191a582d85dcee1631c`; terminal status **succeeded**.
- Current HTML SHA-256: `0c662bbd92bd699659fa0747ce99f03a14914fd0fe31fdc661f6021370d6c9f7`.
- The original alternatives are preserved byte-for-byte in `explorations.html`, SHA-256 `8cd15a23dd952297c01b9aebeaded5ea4b7d402ffab9b5fc05594ed8be0bf433`.

### Research and design corrections

The current transformation creation flow was opened in live Chrome: the empty Transformations board, recipe gallery, vendor overtime recipe, and four-step composer. Its unsaved draft was discarded; no rule was saved. Source review covered `pb_integrations`'s RuleComposer, the mapping source-chip implementation, the scheme's source-lane ordering, the shared declared-source plan, the resolver's emptiness test, rule defaults, and remaining-column reconciliation.

The revised design corrects the first POC's one-source replacement simplification. It preserves multiple declared kinds and relative rank tags, with first-choice/fallback semantics from the scheme order. A source from another kind is added without discarding existing candidates; changing the same kind is a previewed replacement. Scheme ordering and read-lane switches get an impact preview, including record write ownership. Zero and False are supplied values; a missing value is not presented as zero. Pay-run inputs remain last.

The final primary navigation item is Journey. Its global entry opens the holistic view. Trace is a separate focused explanation. A component-opened Journey announces focus and offers Show whole Journey. The intended production implementation reuses the existing Journey board; this HTML uses an illustrative interactive recreation with actual local relationship paths.

The proposed rule builder keeps the existing four-part logic and advanced capabilities, but improves recipes, scope, evidence, missing-data/error states, and optional output binding. A rule can be saved unconnected and explicitly unverified when there is no synced data. Connecting requires a valid reviewed result/type. Existing spreadsheet fallback survives binding. The 18-area feature check distinguishes implemented POC interactions from existing production tools to retain.

### Revision 2 validation

- **63 behavior/invariant checks** passed against the actual revised HTML handlers in jsdom; JavaScript syntax and Git whitespace checks passed.
- Chrome tested the deployed version's zero-vs-blank fallback, ranked sources, scheme priority impact/save/Undo, and restoration of scheme order.
- Deployed wizard: No synced data showed Unverified; simulated error showed its default and fallback warning; sample records produced 5 hours from 2 matching rows; save-and-connect retained spreadsheet fallback.
- Deployed Journey: final primary navigation order was Connections / Transformations / Journey. It displayed all 12 demo components, the newly saved rule, and **17 non-degenerate relationship paths** with no NaN/undefined coordinates. Component focus announced its scope; Show whole Journey restored all 12 rows.
- Deployed text creation reused Shift note and added contract storage without replacing its file source. New amount creation previewed 450,000 VND and then showed No active source after creation rather than inventing a resolved value.
- Responsive checks at **390 × 844** covered local desk, Journey, and rule builder, plus the deployed wizard. No page-wide horizontal overflow occurred; the mobile result summary was visible. The temporary viewport override was reset.
- Chrome error logs were empty. The published demo was reset and left on What changed.
- Task-owned source/publication directories contained **zero local PNG files**. Screenshots were inspected in memory; product assets and user images were not removed.
- Branch/worktree checks preserved the same unrelated workbook deletions and Singapore directory. The complete current static Site state, including archived alternatives, was packaged from its pushed source; both HTML hashes match the repository.

Only the private design-review Site is in deployment scope. No Odoo source, database, source-priority setting, integration job, inactive cron flag, or mail setting was changed. Production implementation remains pending the user's revised-design review.
