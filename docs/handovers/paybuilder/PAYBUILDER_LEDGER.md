# PAYBUILDER — ledger (rules, rulings, gotchas)

Every PAYBUILDER document references this file. Append; never rewrite history. IDs are stable.

## 1. Standing rules (bind every line of code and every word)

| ID | Rule |
|---|---|
| R1 | **White-label:** "Odoo" never appears in anything a user can see or receive (labels, help, toasts, errors, emails, reports, manifest name/summary, `.po` msgstr). Technical identifiers untouched. |
| R2 | **Plain words on screen:** DESIGN §3 vocabulary. No code, column letter, formula text, model name or ticket id on any screen or in any message. |
| R3 | **Design bar:** "extreme WOW, intuitive, out-of-this-world experience, best in class" — hero moment, zero dead-ends, motion with purpose, keyboard ergonomics. Lucide icons only, no emoji, no gradients, one solid primary button per surface, brand indigo `#5A4BB0`. |
| R4 | **One addons directory** `/odoo/odoo-server/addons`; five databases payobook, payobook_template, p0clone, rize, sudima; **never abm**. Release only through `tools/release.sh`. Read `/opt/deploy-notes.md` first. |
| R5 | A screen is not done until used in a real browser with the console open (all states, three languages, the widths in the handover). |
| R6 | English, Vietnamese (vi_VN), Indonesian (id_ID) from the start; three markers per `.po` entry; append as text. |
| R7 | A screen change updates its lessons (pb_learn) in the same programme. |
| R8 | One feature = one commit, explicit file staging, pushed. No credentials, no client names, no real personal data in the repo. Demo records are prefixed `DEMO`. |
| R9 | Demo data on payobook is never deleted. Nothing is created on rize or sudima. |
| R10 | Whatever is possible from the back end must be possible from a screen (the per-person switch, main pay amount and period all have a screen in Formula Studio). |
| R11 | One pay-band rule: gross / deductions / take-home / employer cost are read from `pb_pay_totals()`, never summed in a screen. |
| R12 | No total ever adds two currencies. |

**D11 (owner, 2026-11-28).** The new contract and its preview use the pay scheme approved for the person. The team supplies a fallback when the person has no scheme. Preserve the existing resolver’s work-segment, advance and final-settlement rules.

**D12 (owner, 2026-11-28).** Include Sudima in every release alongside payobook, payobook_template, p0clone and rize.

## 2. Owner decisions (2026-11-28) — see DESIGN §2 (D1–D9). Do not re-ask.

**D10 (owner, 2026-11-28).** An explicit main pay choice wins. When a per-person annual amount drives take-home and a separate wage mapping is only informational, HR enters the annual amount once and sees its monthly equivalent before deductions. Apply this for every tenant using the scheme's own rules.

## 3. Architect rulings (tell the owner at closeout, in plain words)

| ID | Ruling | Why |
|---|---|---|
| A1 | On a scheme whose headline is not the contract wage, `hr.contract.wage` is written as the headline per month (yearly ÷ 12). | The platform requires a wage; lists, bands and letters read it; the scheme does not. |
| A2 | The live block is worked out record-free by the existing compiled engine; the right column keeps the real-records example. A test proves they agree on standard schemes; a muted note explains a difference, neither number is hidden. | 3 ms vs 1–1.5 s; D6 forbids touching the right column. |
| A3 | "Change pay" is sent through Change job's pay change (dated, approved, scheduled), not the contract panel's in-place save. | Lines have no dates; only that path dates a change (FACTS §I). |
| A4 | Plain-words explanations are generated on the server from the formula tree with translatable templates. No external LLM, no formula text to the browser. | Privacy; HR officers have no read on rules; three languages. |
| A5 | The per-person switch warns with a head-count before it is flipped on a live scheme, because flipping it turns the amount to 0 for everyone without a contract amount. No approval step is added in this build. | FACTS §M2; open question for the owner. |
| A6 | The joining page shows `Your pay` only when the company's existing "People can see their own pay explained" setting is on. No new switch. | One setting for one idea. |
| A7 | Text-kind components are not Pay Builder lines in this build. | Needs a different editor; none drive pay. |
| A8 | "Build from a total" and the contract panel's old "Work back from take-home" door stay. | Not asked to remove; ask at closeout. |
| A9 | Typed amounts ride in the existing draft key `usual`; what-if amounts never leave the browser except as an argument to `work_out`. | No new plumbing through approval payloads (NH8). |

## 4. Gotchas (inherited ones that will bite; add new ones below with the next id)

| ID | Gotcha | Source |
|---|---|---|
| PB1 | A contract component with **no line** is 0 in the pay run; `default_value` is used only by the automatic fill on a new contract and only when non-zero. | FACTS §B.2, §M2 |
| PB2 | `_pb_usual_answer_rules()` excludes zero defaults and must stay that way (the automatic fill uses it). Use the new `_pbpb_person_rules()` for what HR may type. | FACTS §B.3 |
| PB3 | Formula errors evaluate to 0 silently. Run `diagnose` before showing a figure. | NH52, FACTS §D.1 |
| PB4 | Pay totals are per payslip: build in-memory lines inside `hr.payslip.new(...)` or every total is 0. | FACTS §F, §M8 |
| PB5 | `0 in (None, '', False)` is True: an explicit 0 must be tested with `is None`. | NH12 |
| PB6 | HR officers have no read on schemes or rules: compute under sudo behind the home's gate, return plain values. | NH6, FACTS §E |
| PB7 | Approval payloads are replayed by another user later: JSON-plain values only, no record ids that may vanish without a refusal sentence. | NH8 |
| PB8 | `write_date` does not move inside one transaction: hash rule content for cache keys. | NH53 |
| PB9 | Contract-line templates are global by code (no company) and carry bounds that raise. Validate bounds before approval. | FACTS §C.1, §M10 |
| PB10 | The msgid "Contract component" is shared by the source chip; the editor needs new msgids. `id_ID.po` lacks the editor's words today. | FACTS §G, §M13 |
| PB11 | `pb_contracts` must not import or depend on the formula engine; pay doors come in through a registry. | FACTS §I, §M15 |
| PB12 | Component amounts in the contract panel are visible to every reader while the wage is masked. Do not widen this: the `change` home needs "may see pay". | FACTS §I, §M7 |
| PB13 | Never NaN or "" into reactive state from an amount box; never a new `markup()` per render; no JS globals in templates; `_t` with a literal first argument and the exact import. | WS18, OWL flicker, NH11, WS39/40 |
| PB14 | Sass `min()/max()` break the bundle: use `calc()`/`unquote`. | WS11 |
| PB15 | Local: asset bundles are not rebuilt by themselves; `--test-enable` hangs after post-tests; post_install tests run only for `-u`'d modules. | NH44, NH39 |
| PB16 | Public pages: plain values from Python, `[hidden]` rule, the website's `editable` name. | RC49, RC72, J-10 |
| PB17 | Upgrading `pb_hr_payroll_formula` upgrades a very large tree: keep new fields in `pb_pay_builder`. | FACTS §K |
| PB18 | The main checkout is ~180 commits behind `origin/19.1`: build only in a worktree from origin. | FACTS §K |
| PB19 | A wage mapping can point to an informational line that does not feed take-home. When choosing between wage and a per-person headline, check which input feeds the take-home line. | D10, read-only scheme check and synthetic reproduction |
| PB20 | The real-records hire preview fills the contract before it assigns a person's own scheme. An unmapped team can therefore supply different usual amounts. Compare the two paths on a team covered by the test scheme, and show the existing difference note when record-derived amounts diverge. | T17 and the hire preview's rolled-back contract creation |
| PB21 | The full 400-visible-line fixture spends more than 60 ms in the existing pay-band totals operation alone on this test machine. Time the unchanged totals separately when exercising the slow-machine guard. | T18, separate baseline and facade timings |
| PB22 | With multiple live schemes and no covering team assignment, preview and hire can both omit the selected scheme's untouched usual amounts. A single-scheme company used them correctly. The real payroll reader then pays the values saved on the contract. | Isolated rollback probes on one- and two-scheme DEMO companies |
| PB23 | When an explanation points to an earning below a folded section, open the section and move keyboard focus after its rows reach the page. A single animation frame can run before the target exists. | Chrome walk on a 400-line DEMO scheme |
| PB24 | The component editor submits the whole draft. An unchanged formula, constant or input type in that draft can trigger the live money approval rule. Omit only those unchanged fields on input rules. A genuine money-field change still goes through its existing gate. | Manager Chrome save and T38 |
| PB25 | The Studio Health tab also loads accounting choices. A scheme manager can edit a scheme without read access to journals. Check read access before listing optional accounts or journals, so scheme settings remain available with the manager's actual rights. | Manager Chrome walk and T41 |
| PB26 | Document Studio renders offer lines using its language-specific table instead of Hiring's table method. Apply the signed pay wording to the table returned by either renderer, and keep the existing letter language and escaping. | T46 |
| PB27 | When Add employee supplies Hiring with the approved contract, the legacy offer component importer is skipped. Explicit zero and positive values reach one contract line each through the studio. | T50, real approval and contract |
| PB28 | A contract or joining card asks which scheme pays the full month. Use the same company main cycle and person-selection context as the employee's Paid by field, so a personal end-of-month scheme still wins. Missing contract amounts count as zero. | T52, W5 and W7 |
| PB29 | The contract drawer's wage cell handles Enter and the drawer handles Escape in the capture phase. A nested Change pay button must keep Enter and give the dialog ownership of Escape until it closes. | Keyboard W5 |
| PB30 | A minimal Contracts install has no configured Contract changes approval process and can lack component history. Compare isolated suite results with the identical module set on the release branch. The drawer finds Change pay only if the optional bridge is installed. | T57 |
| PB31 | Pasted amounts can have foreign grouping even when the person’s screen uses local separators. Two decimal marks cannot form a fraction. Preserve all digits for complete Western or Indian groups before applying the local display format. | Vietnamese Chrome pay-change walk and the shared formatter test |
| PB32 | Learn’s generated lessons come from the tutorial authoring file. Keep the practice wage anchor, and reveal the fixture’s precomputed monthly example only for the matching wage. | P5 generator check and engine-verified example |
| PB33 | A scheme can identify standard working days and paid-day equivalents by its application source while importing the real figures from a pay file. For a full-month example use the existing standard-days helper when the day input is unresolved. Preserve explicit values, including zero, and keep the real pay-run reader unchanged. | Live India preview and T17/T17b |
| PB34 | Imported percentage constants can carry the automatic money classification. A fractional multiplier explicitly labelled with a percent sign must keep its percentage in the explanation. Preserve a manager’s explicit unit choice. | Live monthly allowance and T21b |
