# Pay Builder implementation report

**Status**  The owner approved the annual headline on 2026-11-28. The Add employee candidate has been built and tested locally. The owner confirmed the person’s pay scheme takes priority and included Sudima in all releases. The corrected contract fill passed the person-priority checks in Chrome and through a real local payroll calculation. The Formula Studio switch passed its local checks. The offer and signed handoff passed local verification. Change pay, the public joining card, lessons and deployment are pending. This is an interim report.

## 1. Work completed

Created a fresh worktree from the fetched release branch. The owner confirmed the design pack should retain its original wording. Commit `d6d53af12` contains all six files, verified byte for byte against the supplied copies. Commit `d4f37d8c3` records the annual headline decision. Both documentation commits are on `origin/paybuilder`. P1 was pushed to the feature branch in `f482ddfd7`. Production still runs the base versions.

| Module | Base | P1 candidate | Change |
|---|---|---|---|
| pb_pay_builder | New | 19.0.1.0.0 | Scheme classification, compiled monthly calculation, explanatory chips, take-home search, shared pay block, language files and tests |
| pb_new_hire | 19.0.1.8.2 | 19.0.1.9.0 | Step 3, review, validated contract amounts and approval replay |
| pb_formula_studio | 19.0.1.217.0 | 19.0.1.218.0 | Reuse classified line metadata in the existing engine and open the specified component from its explanation |

The following existing files changed during P1.

- In `pb_new_hire`, the manifest adds the shared module. `models/studio.py` validates the headline and component bounds, derives the monthly wage, and prepares numeric contract answers including zero-usual amounts. `models/create_ext.py` replays the accepted answers and passes the approved personal scheme and its own advance to the existing automatic fill for this contract only. Old payloads still follow their existing fallback. `models/payslip_example.py` checks the same headline before creating its temporary example.
- In the same module, `static/src/js/new_hire_studio.js` connects the draft, readiness and example to the shared block. `step_pay.js` hosts it. `step_check.js` shows the agreed period and typed lines. `studio_util.js` reuses the shared money and icon helpers. `static/src/xml/new_hire_studio.xml` replaces the two old cards and retains the pay-scale slot. `i18n/pb_new_hire.pot`, `vi_VN.po` and `id_ID.po` carry the new words. `tests/test_pay_builder.py` and `tests/__init__.py` cover approval, bounds and agreement with payroll.
- In `pb_formula_studio`, `models/take_home.py` accepts optional preclassified lines. Existing engine callers keep their original path. `static/src/js/formula_studio.js` selects the component on arrival. The manifest records the version.

## 2. Test baseline

The local runner used the seven requested module tags, one exact database filter, and the official framework addons ahead of the fresh worktree. The locally cloned database and filestore were isolated from the browser-walk fixtures. These are results for the release branch before implementation. The table records the original seven suites. The additional P1 tests run on separate local databases.

| Module | Run | Passed | Failures | Errors | Skipped |
|---|---:|---:|---:|---:|---:|
| pb_new_hire | 178 | 177 | 1 | 0 | 0 |
| pb_formula_studio | 560 | 547 | 10 | 1 | 2 |
| pb_pay_package | 20 | 20 | 0 | 0 | 0 |
| pb_contracts | 65 | 64 | 1 | 0 | 0 |
| pb_job_change | 31 | 30 | 0 | 0 | 1 |
| pb_joining | 73 | 71 | 0 | 2 | 0 |
| pb_hiring | 532 | 520 | 9 | 2 | 1 |

Runner output — 21 failed, 5 error(s) of 1459 tests when loading database 'pb_builder_base_1795829993'

- Failure — `pb_new_hire.test_p7.TestP7Places.test_c6_places_is_quick_on_a_rize_sized_company`
- Failure — `pb_formula_studio.test_journey_view.TestJourneyView.test_01a_every_via_has_exactly_one_bucket`
- Failure — `pb_formula_studio.test_journey_view.TestJourneyView.test_04a_connections_is_the_cold_start_and_journey_remains_available`
- Failure — `pb_formula_studio.test_mapping_catalogue.TestMappingCatalogue.test_02_every_field_lands_in_exactly_one_lane`
- Failure — `pb_formula_studio.test_mapping_values.TestMappingSelectionValues.test_02_every_card_on_the_right_carries_the_same_metadata`
- Failure — `pb_formula_studio.test_mapping_values.TestMappingSelectionValues.test_06_the_dropdowns_and_the_search_offer_what_the_board_offers`
- Failure — `pb_formula_studio.test_net_pay_candidates.TestNetPayCandidates.test_01_the_screen_asks_because_nothing_names_net_pay`
- Failure — `pb_formula_studio.test_one_mapping_home.TestOneMappingHome.test_the_employee_toolkit_is_scoped_to_the_employee_board`
- Failure — `pb_formula_studio.test_one_mapping_home.TestOneMappingHome.test_the_payroll_lane_can_actually_be_revealed`
- Failure — `pb_formula_studio.test_one_mapping_home.TestOneMappingHome.test_the_tabs_read_as_the_sentence_not_as_the_adapter_names`
- Failure — `pb_formula_studio.test_runsrc_pc_board_lane.TestRunsrcPcBoardLane.test_14_two_sources_render_two_chips`
- Error — `pb_formula_studio.test_one_mapping_home.TestOneMappingHome.test_the_formula_studio_button_opens_the_full_screen_board_pre_scoped`
- Skipped — `pb_formula_studio.test_journey_view.TestJourneyView.test_03d2_a_scheme_that_names_no_connection_says_its_wires_are_inert`
- Skipped — `pb_formula_studio.test_wdgap_w2c_take_home.TestW2cTakeHome.test_20_demo_world_forward_check`
- Failure — `pb_contracts.test_cd1_contract_360.TestCd1Contract360.test_01_payload_carries_every_top_level_key`
- Skipped — `pb_job_change.test_wdgap_s8_merge_seams.TestWdgapS8MergeSeams.test_m3_transfer_and_cost_centre_history`
- Error — `pb_joining.test_jobs.TestDaily.test_t63_erase_at_thirty_days_for_both_closed_states`
- Error — `pb_joining.test_studio.TestLanding.test_t50_t58_t59_t60_verified_signed_copy`
- Failure — `pb_hiring.test_client_review.TestClientReview.test_hiring_only_cannot_read_access_directory`
- Failure — `pb_hiring.test_interviews_p5.TestRecruitInterviewsP5.test_07b_without_google_nothing_changes`
- Failure — `pb_hiring.test_joining_p6.TestRecruitJoining.test_11_the_numbers_filters_funnel_ageing_leadership_and_exports`
- Failure — `pb_hiring.test_offer.TestTheCover.test_t7_who_is_asked_to_agree_it_is_said_out_loud`
- Failure — `pb_hiring.test_privacy_p4.TestRecruitPrivacy.test_02_the_manager_sees_the_card_and_a_sentence_until_shared`
- Failure — `pb_hiring.test_privacy_p4.TestRecruitPrivacyFiles.test_02_tokenised_cv_link`
- Failure — `pb_hiring.test_registers_p9.TestRegistersP9.test_06_the_overview_tiles_equal_the_register_counts`
- Failure — `pb_hiring.test_registers_p9.TestRegistersP9.test_08_the_hub_names_the_two_registers_between_overview_and_interviews`
- Failure — `pb_hiring.test_stages_p1.TestRecruitStages.test_13_set_up_has_six_cards_and_none_is_a_dead_end`
- Error — `pb_hiring.test_privacy_p4.TestRecruitPrivacy.test_02b_unsharing_regenerates_the_file_tokens`
- Error — `pb_hiring.test_privacy_p4.TestRecruitPrivacy.test_08_the_resume_bank`
- Skipped — `pb_hiring.test_client_review.TestClientReview.test_demo_migration_is_scoped_and_idempotent`

### P1 candidate checks

Before the person-priority correction, the product worktree ran 41 feature and static checks. Thirty-nine passed, one failed and one used the permitted slow-machine skip. All numbered functional cases T1–T34 passed apart from T18’s timing target. The additional T33b test failed and reproduces the real contract discrepancy described below. T34 checked the normal refusal delivered to HR before any proposal was created. The 400-line measurement for this run was 514 ms, with 256 ms in the existing pay-band totals operation alone. Earlier runs measured 549 ms and 564 ms.

The earlier full run of the three touched modules finished with 778 tests. It recorded 764 passes, ten failures, one error and three skips. The ten failures and one error were all present in the Formula Studio baseline. The existing Add employee performance case passed on this run. The additional contract discrepancy test was added after this runner loaded its test list. The final 41-case run from the product worktree included it and reran the entire new module after the long-range explanation and keyboard-focus changes.

| Module | Distinct candidate tests | Passed | Failed | Errors | Skipped |
|---|---:|---:|---:|---:|---:|
| pb_new_hire | 182 | 182 | 0 | 0 | 0 |
| pb_formula_studio | 560 | 547 | 10 | 1 | 2 |
| pb_pay_builder | 37 | 36 | 0 | 0 | 1 |
| **Final P1 full-suite run** | **779** | **765** | **10** | **1** | **3** |

Following the owner’s confirmation, a 48-case run combined all 41 feature checks, six existing hire/assignment tests and the existing dated scheme priority test. It had 47 passes, zero failures, zero errors and one performance skip (290 ms, of which the existing totals operation took 134 ms). The corrected candidate covered both ordinary approval and the direct approved-hire route. The real payroll reader returned lunch 730,000 and insurance enabled. The builder, preview and actual payslip all returned ₫25,952,500. The same answer held with a different active scheme assigned to the team. An old approval carrying no personal choice retained the team fallback. In Chrome, the quoted take-home matched the right-hand payslip for both an unmapped team and a team with a different scheme.

After the correction, the full run of all three touched modules executed 779 tests in one run. All 182 Add employee cases passed. The 10 failures and one error were already present in Formula Studio. Of three skips, two were in its baseline. The new 400-line timing was 295 ms in this run, including 133 ms for the mandatory existing totals operation.

The other four baseline modules have no P1 changes. Their phase-specific checks remain with the phases that change them.

## 3. Headline selection

The specified headline order prefers any monthly wage mapping. The active India scheme has a hidden informational line mapped to the contract wage. Its annual fixed amount drives take-home. The documented order would pick monthly wage and fail the release walk. A local synthetic scheme with the same mapping shape confirmed this with the existing wage resolver and dependency graph.

The owner authorized the supplied design pack to be committed verbatim.

## 4. Facts verified

- Read-only queries confirmed the India scheme is active. Its annual fixed amount is a per-person money input with a zero usual amount. It feeds take-home. The separate wage-mapped line is hidden from the payslip and has no path to take-home.
- On this installed module combination, Add employee handles the signed offer’s contract before the package module. In a rolled-back local probe, the originating hire returned the existing contract and called the package line writer zero times. An end-to-end test of the finished feature is still required.
- With the current contract proposal payload shape, the contract approval detail raised `KeyError` in a local probe. The inbox wrapper returned `None`. The probe used synthetic data. Individual live approvals were outside the probe.
- The Add employee dependency tree contains Formula Studio, the formula engine, import kit and scheme map. Pay is installed across the five release targets but is outside that tree. Including it adds one custom module and zero standard ones. Change job would also add the organisation chart to a standalone Add employee installation.

## 5. Browser and engine checks

Chrome opened all four prototype homes on both schemes. The existing compiled engine matched each prototype on local synthetic data.

| Agreed amount | Gross | Deductions | Take-home | Company contributions |
|---|---:|---:|---:|---:|
| ₹1,200,000 yearly | ₹98,250 | ₹3,200 | ₹95,050 | ₹3,000 |
| ₫30,000,000 monthly | ₫30,730,000 | ₫4,777,500 | ₫25,952,500 | ₫6,450,000 |

Chrome also verified the prototype’s keyboard-opened annual-pay explanation, chip-to-input focus and temporary arrears adjustment. A ₹100,000 take-home target returned ₹1,260,000 yearly and ₹100,050 monthly take-home. The reference page fit 1180, 820, 600 and 400 px widths. The read-only phone example had zero visible pay inputs at 360 px.

In the current Add employee screen, Chrome showed ₹1,050 take-home for the synthetic yearly-package hire. The usual ₹1,250 allowance and ₹200 deduction survived. A direct call with an explicit annual amount confirmed that the existing hire path discarded that amount. The test screenshot was inspected and removed.

Seven local fixtures cover a simple wage, wage with allowances, yearly package, file-driven pay, missing take-home, broken formula and 400 rules. On this machine the warm 400-visible-line run of the existing engine, in-memory totals and diagnostics took 930–1,018 ms. This is a pre-implementation engineering measurement. The new facade measured 526 ms for 400 visible lines on a warm run. The same run measured 245 ms for the required pay-band totals operation alone. T18 used the allowed slow-machine skip. The 60 ms target was missed.

In the P1 product, the annual input displayed ₹12,00,000 and the monthly helper displayed ₹1,00,000 before deductions. The block and the existing right-hand payslip agreed on ₹95,050 take-home. A take-home target of ₹1,00,000 produced ₹12,60,000 yearly and ₹1,00,050 take-home. A keyboard-opened Basic explanation supplied its rate and this hire’s numbers, and its input chip returned focus to the annual box.

The monthly Chrome walk exercised change, reset, add-from-bar, temporary overtime, three explanations, the progressive-tax table, an empty headline and step 7. The approver then opened a pending DEMO hire in the normal Approvals inbox. The proposal displayed the phone allowance HR had entered, ₫500,000. Chrome reported no page errors. With the isolated local tenant at its employee limit, the screen showed the plan’s refusal and explained that an approved hire waits for an available place. A wage-only scheme showed one pay row and ₫10,000,000 take-home on a ₫10,000,000 wage. The file-driven scheme showed ₫50,000. The broken and missing-net cases left take-home blank. An HR reader saw plain amounts. In a DEMO company with no schemes, the monthly wage remained available and the screen explained why it could not calculate the month.

A separate keyboard walk tabbed from the headline through Work back, both additional questions and the Basic row. Enter opened its explanation and Escape closed it with focus still on Basic. Chrome showed five placeholders while the first answer was held, kept inputs usable and previous rows visible during a slow refresh, retained the wage through a simulated service refusal and recovered through Try again. A 400-rule scheme opened with twelve visible rows, expanded to 399 and folded back to twelve. **Show the 14 lines** opened the members of a long sum, and choosing the last one expanded the folded list and put keyboard focus on the correct earning.

The monthly screen showed ₫25,952,500 in English, Vietnamese and Indonesian. All three passed the reduced-motion and width checks at 1440, 1180, 820, 600 and 400 px without horizontal overflow. The annual walk also ran with motion enabled. Chrome inspection identified an inherited 14 px headline style; the second comparison measured the specified 26 px. Test images were captured under `docs/handovers/paybuilder/shots/p1-annual-comparison.png`, `p1-annual-{width}.png` and `p1-{en_US,vi_VN,id_ID}-{width}.png`. These captures and the temporary comparison images were removed after inspection under the repository’s screenshot cleanup rule.

### P1 assessment against the design

| Owner’s criterion | Local assessment | What the walk established |
|---|---|---|
| Type the agreed amount and see the month | Meets on mapped teams | One annual entry updated the pay lines and take-home. The right-hand example agreed. |
| Plain language | Meets on the screens walked | The headline, monthly equivalent, allowance labels and tax steps were readable in the selected language. Scheme-supplied line names kept the wording of their scheme. |
| Every state gives HR a way forward | Meets on checked paths | The payroll discrepancy with an unassigned team was corrected. An unassigned team and a team with a different scheme both passed the Chrome and payroll checks. |
| Motion with purpose | Locally checked | The regular-motion annual walk showed the amount changes. The reduced-motion walks recalculated at all five widths. |
| Keyboard operation | Locally checked on the main interactions | Enter opened a formula, its chip focused the input, and HR could change and reset an allowance and return to the draft. |
| Best in class across the four homes | Unverified | Only Add employee has been built. The large scheme also exceeded the 60 ms target. |

The other three homes and all live walks are pending.

## 6. Release

Production access was read-only. The nine existing modules checked had identical installed versions across the five targets. The release script, live demos and release verification have not run.

## 7. Ledger

New findings are listed above. The ledger records D10 and PB19–PB23.

## 8. Owner decision

On the agreed annual scheme, HR enters ₹12,00,000 in **Annual fixed pay**. Payobook shows ₹1,00,000 a month before deductions and works out the monthly breakdown. That example has ₹95,050 take-home. A new company’s first box follows the selected scheme. Its explicit main pay choice takes priority. A scheme driven by monthly wages shows **Monthly wage**. A company with no scheme yet can enter the wage and gets an explanation.

### Person’s scheme and active release scope

- On an unmapped team in a DEMO company with two active schemes, HR selected the one with a ₫730,000 lunch allowance and insurance. For a ₫30,000,000 wage the block showed ₫25,952,500 take-home. The preview showed ₫27,850,000. A second, independently created hire through the real send path saved an empty set of contract amounts. The real payroll input reader returned zero for lunch and insurance and calculated ₫27,850,000. With only one active scheme, both usual amounts reached the contract. All records in these probes were local and rolled back.
- The owner confirmed the existing person-first priority. For ordinary pay, a dated work segment with its own scheme takes priority, followed by the person’s active assignment, then the team when there is no personal assignment. Final settlement has its own rules. When the person has their own scheme, a team cannot supply an unassigned mid-month advance. Commit `5a31a6fcf` introduced the person priority on 2026-11-26. The production resolver file matched the repository byte for byte on verification.
- The owner included Sudima in every release. Commit `f8791a01b` updated the standing instructions on `19.1`. The release runner already defaults to payobook, payobook_template, p0clone, rize and sudima.

### Formula Studio

The input editor offers two choices, whether HR keeps an amount on each person's contract or it arrives with each month's data. Before a change to a live scheme, the screen counts the people affected, allows an HR reader to see up to twenty names, and lets the manager keep the current setup or confirm. A stored zero counts as an amount already entered. The scheme's Health tab carries the main pay selection alongside its existing tax-year setting.

The shared module advances from 19.0.1.0.0 to 19.0.1.1.0. Its server and component-editor extensions introduce the switch, the month/year control, translations and tests T35–T42. Two existing Formula Studio files changed in this phase. The manifest advances from 19.0.1.218.0 to 19.0.1.218.1, and `models/pb_formula_studio.py` omits accounts and journals from the settings choices when the manager cannot read them. The source switch follows the current manager permission and requires no second person's approval.

The combined local suites ran 605 tests. Formula Studio had 547 passes, ten failures, one error and two skips across 560 tests, the same named results as its baseline. Pay Builder had 44 passes and one slow-machine skip across 45 tests. All eight numbered switch checks passed. The 400-rule run took 325 ms, including 146 ms for the existing totals operation alone. Chrome saved Year, reopened the component to verify it, restored Month and selected and cleared the scheme’s main pay amount as a manager with no journal access.

W3 passed in Chrome in English, Vietnamese and Indonesian. The manager opened both warnings, expanded the affected names, kept the original source, then confirmed and saved each direction. Each language fit 1440, 1180, 820, 600 and 400 px with reduced motion. Keyboard Space and Enter operated the choices and confirmation. The captured panels at `docs/handovers/paybuilder/shots/p2-warning-{en_US,vi_VN,id_ID}.png` were inspected and removed under the repository cleanup rule. Reopening an editor while its previous save was refreshing could discard a fast click. The edit button now waits for that save to finish.

### Hiring offer and signed handoff

The offer editor opens the shared Pay Builder in a dialog and keeps the earlier Build from a total button. Use these lines recomputes the usual month on the server, writes positive monthly earnings, and retains separately entered items. It saves the entered values, including zero, and the month’s agreed gross pay and take-home under Hiring’s existing pay-field permissions. The letter preview and candidate letter can show the table and take-home or a single gross-pay sentence. Temporary amounts stay in the calculator.

A signed offer can supply the wage, selected scheme and per-person values in Add employee or the Joining handoff. The scheme must still be available for the person's country and the offer must use the same currency. Applying the agreement through a local hire produced exactly one contract line for each entered code. The old offer importer did not run.

Existing module edits in this phase are as follows.

- `pb_pay_package` advances from 19.0.1.1.1 to 19.0.1.2.0. The manifest adds the shared module and the dialog assets. The offer extension owns saved money, validates access and persists earnings. The older total action clears the previous builder snapshot when chosen instead. The offer panel, letter preview, translations and T43–T46 are in this module.
- `pb_new_hire` advances from 19.0.1.9.0 to 19.0.1.9.1. The Hiring draft reader brings eligible signed values across under its existing access check. The studio client keeps their origin through an unsent draft reload.
- `pb_joining` advances from 19.0.1.0.1 to 19.0.1.0.2. Its checked-joining draft uses the joiner’s actual country when bringing across a signed offer. Its studio extension uses the same origin markers. T47–T50 include an HR officer who has no Hiring rights.
- `pb_doc_studio_hiring` advances from 19.0.1.2.0 to 19.0.1.2.1. Its offer renderer applies the optional pay wording to its own translated table. Its additional baseline was 20 passes out of 20.

T43–T50 passed together, eight out of eight. The server tests exercised the existing offer gate, replacement of a previous set, currency mismatch, both letter renderers, a mismatched or retired scheme, checked joining, and an actual hire through approval.

The full suites for this phase ran 303 tests. Add employee passed 182 of 182, the offer package 24 of 24 and Document Studio's offer extension 20 of 20. Joining passed 75 of 77. Its two errors matched the named baseline cases above. The candidate's public Accept action and HR's signed-copy workflow completed in the local browser walk. The local machine lacks the PDF converter used by the server. Chrome printed the real offer letter table to a DEMO PDF for that walk. The production PDF converter remains a deployment check.

On the monthly DEMO offer, a wage of ₫30,000,000 plus lunch and a ₫500,000 phone allowance produced ₫31,230,000 gross and ₫26,377,500 take-home. The gross-only and itemised letter views rendered in all three languages. Temporary overtime stayed out of the saved offer. After acceptance and signature, Add employee showed both the wage and the phone amount with their signed-offer labels. At 1440, 1180, 820, 600 and 400 px, the dialog fit without horizontal overflow. A side-by-side check with the offer prototype led to the 38 × 22 px letter switch, the heading for the itemised month and the desktop panel width.

W4 captures at `docs/handovers/paybuilder/shots/p3-letter-{en_US,vi_VN,id_ID}.png` and the temporary prototype pair were removed after inspection under the repository cleanup rule.
