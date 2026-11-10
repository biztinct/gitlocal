# Workflow Studio design review pack

This pack gives an independent reviewer the product requirements, design decisions, implemented behavior, prototypes, source map, limitations and recorded verification for Payobook Workflow Studio. Start with the prompt and design brief; use the original POC to explore the interaction direction, and the implementation source to establish what actually ships.

**Baseline:** 10 November 2026, branch `19.1`, implementation commit `f68945ecc39b2845f00f09a77e3fa2941ffe640c`, `pb_lifecycle` version `19.0.1.9.0`. Documentation added after this baseline does not change application behavior. This is a review of the implementation at that commit, not a promise that every prototype feature has shipped.

## Read in this order

| Order | Artifact | What it provides |
| --- | --- | --- |
| 1 | [Second opinion prompt](SECOND_OPINION_PROMPT.md) | Ready to paste into another session; includes context, artifact links, review questions and requested output. |
| 2 | [Design and implementation brief](DESIGN_REVIEW.md) | The current product, user journeys, architecture, data model, permissions, execution semantics and limits. |
| 3 | [Decisions and open questions](DECISIONS_AND_GAPS.md) | Requirement history, alternatives, tradeoffs, prototype differences and areas to challenge. |
| 4 | [Artifact and source map](ARTIFACT_MAP.md) | Which HTML, JavaScript, Python, XML, Markdown and text files answer each design question. |
| 5 | [Verification and release evidence](VERIFICATION.md) | What was tested and deployed, what the evidence does not establish, and how to review safely. |
| 6 | [Original Workflow Studio POC](../../workflow-studio-poc.html) | Self-contained browser prototype with fictional data, three design views and embedded research. Useful for interaction exploration, not an exact copy of the latest deployed UI. |
| 7 | [Approval Matrix POC](../../approval-matrix-poc.html) | Separate approval configuration experience that Studio must complement. Its adjacent `approval-matrix-poc/` assets are required. |
| 8 | [Implementation narrative](../IMPLEMENTATION.txt) | Chronological implementation notes, including premium templates, filters, wrapping journeys and record-stage integration. Later dated sections supersede earlier descriptions. |

## Which artifact is authoritative

1. Current implementation source at the baseline commit establishes behavior.
2. Recorded test/release evidence establishes the checks actually performed.
3. This review brief explains the intended meaning, boundaries and unresolved questions.
4. The POC and its research explain design exploration; “working” there means working with browser-local sample data.
5. Older handovers explain history and adjacent systems. They do not override current source or repository operating instructions.

In particular:

- The POC says Community `base_automation` was uninstalled during its initial audit. It was subsequently installed and used by the implementation.
- The POC uses “stages” for workflow groups. The current UI calls these **Sections** and reserves **Stages** for native record-stage context.
- [PAUSED-HANDOVER.txt](../PAUSED-HANDOVER.txt) is explicitly historical. Work resumed and was deployed.
- Historical Approval Matrix documents mention retired databases, including ABM. The current active deployment scope is `payobook`, `payobook_template`, `p0clone`, `rize`. ABM remains retired.
- The POC's decision tables, detailed rehearsal, multilingual Hiring template demo and several advanced editor features are not all present in the production Studio.

## Opening the artifacts

The original POC can be opened directly from disk. It contains its own font, styles and scripts and stores fictional drafts in browser storage. The Approval Matrix POC also needs its sibling asset folder; its optional web font uses Google Fonts.

The current application's [HTML entry](../../../../pb_lifecycle/static/workflow/index.html) is **not** an offline demo. It needs an authenticated Odoo session, RPC services and the application wrapper. Open Settings → Workflows → Workflow Studio, or use **View workflow** / **Set up workflow** from a supported saved record. The [public preview URL](https://payobook.com/preview/workflow-studio/) is the historical POC, not the deployed runtime. The application URLs [payobook.com](https://payobook.com/odoo), [p0clone.payobook.com](https://p0clone.payobook.com/odoo) and [rize.payobook.com](https://rize.payobook.com/odoo) require an authorized account; database-specific action IDs are not portable.

The intended review workflow is to paste [SECOND_OPINION_PROMPT.md](SECOND_OPINION_PROMPT.md) into another session with access to `/Users/adity/Documents/GitHub/gitlocal`. That prompt contains full absolute paths and tells the reviewer to read the files directly. No attachment is required. Local paths are accessible only to a session with access to this workspace.

The previously generated `workflow-studio-review-2026-11-10.zip` remains an optional archived snapshot, including the earlier portable prompt. It preserves repository-relative paths and contains the review documents, both POCs, their source/assets, the current `pb_lifecycle` module, selected integration source, adjacent approval design documents and non-secret verification evidence. It is a source review snapshot, not an installable copy of the whole application; it is not needed for the requested same-workspace review.

The bundle's `FILE_MANIFEST.json` records the exact included files, byte lengths and SHA-256 hashes. Credentials, customer databases, filestores, temporary test accounts and screenshots are excluded. Reviewers can assess the supplied code without logging into production. The original screenshots supplied in the conversation are not repository files; their design issues and resulting changes are captured in the brief and decision log.

## Review scope

Evaluate both the chosen design and its actual implementation. Do not assume the recommendation is correct. In particular, challenge the split between module stages and workflow sections; the additional `pb.workflow.*` runtime beside existing lifecycle models; duplicated form/filter UI; component copies versus governed shared components; shared mutable templates versus pinned runs; and the limited reach of overlap detection.

A design review does not authorize deploying code, changing records, publishing workflows, granting access, sending messages or recreating retired environments. Use [SECOND_OPINION_PROMPT.md](SECOND_OPINION_PROMPT.md) for the complete review instructions.
