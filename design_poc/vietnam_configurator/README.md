# Vietnam configuration lab — design POC

Interactive, self-contained deliverable: `public/prototype.html`. Open it directly in Chrome, or use the private Sites root URL in `.openai/hosting.json`'s project. The root route embeds that exact HTML.

This phase is a design prototype. The deployment target is the owner-private Sites project. No Odoo module, tenant or database is in scope. The prototype creates local draft schemas and exports an executable prototype expression tree, not an Odoo import or activation payload.

## Design

Six steps: Basics → Components → Rules → Formulas → Test → Create schema. The first view opens on Components so the proposed change is immediately reviewable. Purple rail, white panels, lavender selection states and compact controls follow the supplied Formula Studio screenshots. Each component can be edited, removed, restored or supplemented with a new component.

The component library retains all 24 earnings (Earning Codes rows 5–28), 8 deductions (Deduction Codes rows 4–11), and 6 plans (Benefits rows 4–9). The role-based allowance table below the earnings is a shared rate table, not extra earnings. The original workbook is unchanged.

Calculation settings use code/name/category, cash/non-cash, tax treatment, insurance base, proration/frequency, plan eligibility, employee and employer costs. Historical payroll examples, source payroll columns, implementation owners/status, provider contacts and posting labels do not become formula switches. Original relevant fields remain visible in the source dialog. No individual payroll or banking records are embedded.

Added: explicit amount sources, fixed/role/hourly/annual formulas, annual exemption balance, qualifying evidence, approved severance entitlement, inherited adjustment references, payment triggers, separate employer costs, benefit links, cost sharing, employer-borne incremental tax gross-up, sample profiles, local drafts, JSON export and a generated formula inspector.

## Source ambiguities and deliberate choices

- `PRIVATE_INS_ALLOW` insurance treatment remains a visible unresolved choice.
- Union dues keep the workbook's company-applied 0.5% with a visible 0.5%/1% conflict. Reviewing a policy does not certify it.
- Private benefits remain review-required despite source “Ready” labels and TBD eligibility/cost cells. Defaults propose enrollment and 100% employer funding, with explicit period-premium inputs.
- Dependant health premium links to `PREMIUM_INS_ALLOW`. Monthly premium allocation replaces the source's unspecified Scheme trigger for this demonstration. Employee and dependant premiums are separate.
- SHUI plans reference the existing employee deductions and produce employer cost only. No duplicate 10.5% deduction. Missing linked deductions create review errors.
- `ADJ_DEDUCT` is a negative earning correction. A source is required for inherited treatment. Current-period corrections do not claim to perform retrospective tax/cap recalculation.
- Every source item starts included. Ad hoc/scheme inputs can be zero; inclusion does not imply a payout for every employee.
- Statutory numeric values are workbook-derived demonstration defaults. The five-band structure and overtime/night/qualifying leave exemptions were checked against the official Law 109/2025 overview; the official Decree 253/2026 listing was also checked. The workbook's insurance-cap URL did not substantiate the cap in the retrieved page. These are not certified rates.

Sources: [official Law 109/2025 overview](https://xaydungchinhsach.chinhphu.vn/gioi-thieu-luat-thue-thu-nhap-ca-nhan-so-109-2025-qh15-119260123145437408.htm); [Decree 253/2026 listing](https://chinhphu.vn/?classid=1&docid=218684&pageid=27160&typegroupid=4).

## Running and verification

- `npm run dev` regenerates the standalone HTML and starts the preview.
- `npm run build` regenerates it and produces the Sites deployment.
- `npm test` checks source completeness, independent sample totals, proration, annual limits, caps, nationality, tax bands, short-term thresholds, cost sharing/gross-up, removal, corrections, annual triggers, zero denominators and JSON round-trip execution.
- Chrome QA covers edit/add/remove/restore, wizard navigation, formula preview, sample scenarios, local schema creation and the formula inspector. Test screenshots are inspected in memory; none are retained as files.

## Production integration proposal

Extend `pb_formula_studio`'s existing `create_config` payload to carry a versioned country pack, component definitions, typed input mappings, effective-dated values and treatment policies. Generate and validate Formula Studio-compatible formulas server-side. Preserve draft status until production review and tests are complete. The POC's custom AST helpers need explicit adapters to the production parser; `productionCompatible: false` documents that boundary in exports.

Remaining integration: employee-specific enrollment/evidence, versioned country rules, pension/permit edge cases, FX and net contracts, historical corrections, multiple short-term payments, annual tax finalization, cross-cycle advance settlement, server persistence and tenant authorization. The cycle selector is schema metadata; mid-month settlement is not simulated. Scenario evidence/enrollment toggles are shared fixtures, not an employee-master design.
