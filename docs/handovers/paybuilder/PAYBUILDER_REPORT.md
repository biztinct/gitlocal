# Pay Builder implementation and release report

Local testing covers all four homes. The final eleven-module regression run is complete. Production verification follows the release.

## 1. What was built

| Phase | Commit on paybuilder | What HR or the employee can do |
|---|---|---|
| Design | `d6d53af12`, `d4f37d8c3` | The first commit preserves the owner’s supplied pack. The second records the approved annual starting amount. |
| P1 | `f482ddfd7` | In Add employee, enter the agreed amount, see a month’s pay, open a calculation, change an allowance or work back from take-home. Approval saves the agreed values on the contract. |
| P2 | `d7f2d9de2` | In Formula Studio, choose where an input comes from. A manager can see how many people a change affects before confirming it. |
| P3 | `60cb015ca` | Use the same builder on an offer, choose how the letter shows pay and carry the signed amounts into the hire. |
| P4 | `6681a6a56` | Date a change from a contract, compare before and after, and send it down the existing approval route. After hire approval, the employee can view their own pay on the joining page. |
| P5 | See the release revision in section 6 | Practice entering a wage in Learn, with an example monthly breakdown. Updated the lesson text, checked translations and removed retired hire-card wording. |

The permanent release scope includes Sudima in `f8791a01b`. The engine, take-home search, pay-band totals and payroll input reader remain the existing payroll implementations. The hire approval now supplies the employee’s selected scheme when the existing fill prepares that new contract.

| Module | Previous version | Feature version |
|---|---|---|
| pb_pay_builder | New | 19.0.1.2.0 |
| pb_pay_builder_change | New | 19.0.1.0.0 |
| pb_new_hire | 19.0.1.8.2 | 19.0.1.9.2 |
| pb_formula_studio | 19.0.1.217.0 | 19.0.1.218.1 |
| pb_pay_package | 19.0.1.1.1 | 19.0.1.2.0 |
| pb_contracts | 19.0.1.17.0 | 19.0.1.17.1 |
| pb_joining | 19.0.1.0.1 | 19.0.1.1.0 |
| pb_doc_studio_hiring | 19.0.1.2.0 | 19.0.1.2.1 |
| pb_learn | 19.0.20.12.0 | 19.0.20.12.1 |

**Existing module edits, by file.** Paths below are relative to the named module.

- pb_contracts — `__manifest__.py`, `i18n/id_ID.po`, `i18n/pb_contracts.pot`, `i18n/vi_VN.po`, `static/src/js/contract_360.js`, `static/src/xml/contract_360.xml`.
- pb_doc_studio_hiring — `__manifest__.py`, `models/offer.py`.
- pb_formula_studio — `__manifest__.py`, `models/pb_formula_studio.py`, `models/take_home.py`, `static/src/js/formula_studio.js`.
- pb_joining — `__manifest__.py`, `controllers/joining.py`, `i18n/id_ID.po`, `i18n/pb_joining.pot`, `i18n/vi_VN.po`, `models/__init__.py`, `models/pay_builder.py`, `models/studio.py`, `static/src/js/studio_joining.js`, `static/src/scss/joining_page.scss`, `tests/__init__.py`, `tests/test_builder_handoff.py`, `tests/test_your_pay.py`, `views/your_pay.xml`.
- pb_learn — `__manifest__.py`, `static/content/learn_content.json`, `static/src/anchors.json`, `static/src/engine/screens.js`, `static/src/journey/journey.js`.
- pb_new_hire — `__manifest__.py`, `i18n/id_ID.po`, `i18n/pb_new_hire.pot`, `i18n/vi_VN.po`, `models/create_ext.py`, `models/hiring.py`, `models/payslip_example.py`, `models/studio.py`, `static/src/js/new_hire_studio.js`, `static/src/js/step_check.js`, `static/src/js/step_pay.js`, `static/src/js/studio_util.js`, `static/src/xml/new_hire_studio.xml`, `tests/__init__.py`, `tests/test_pay_builder.py`.
- pb_pay_package — `__manifest__.py`, `i18n/id_ID.po`, `i18n/pb_pay_package.pot`, `i18n/vi_VN.po`, `models/__init__.py`, `models/offer_builder.py`, `models/offer_total.py`, `static/src/js/offer_builder.js`, `static/src/scss/build_total.scss`, `static/src/xml/offer_builder.xml`, `tests/__init__.py`, `tests/test_pay_builder_offer.py`.

The canonical Learn authoring file is `docs/tutorial_poc/author/data.js`. Its generator reproduced the lesson bundle. Hiring and Change job supply their existing access, signing, approval and dated application methods. Their source files required no edits.

## 2. Tests before and after

Before modifying product code, all seven required suites ran from the release branch on an isolated local copy. Of 1,459 cases, 1,429 passed, 21 failed, five errored and four skipped. The extra Document Studio and Learn suites were baselined before their respective changes. The counts below follow the order **run / passed / failed / errors / skipped**.

| Module | Before | Final |
|---|---|---|
| pb_new_hire | 178 / 177 / 1 / 0 / 0 | 182 / 182 / 0 / 0 / 0 |
| pb_formula_studio | 560 / 547 / 10 / 1 / 2 | 560 / 547 / 10 / 1 / 2 |
| pb_pay_package | 20 / 20 / 0 / 0 / 0 | 24 / 24 / 0 / 0 / 0 |
| pb_contracts | 65 / 64 / 1 / 0 / 0 | 65 / 64 / 1 / 0 / 0 |
| pb_job_change | 31 / 30 / 0 / 0 / 1 | 31 / 30 / 0 / 0 / 1 |
| pb_joining | 73 / 71 / 0 / 2 / 0 | 83 / 81 / 0 / 2 / 0 |
| pb_hiring | 532 / 520 / 9 / 2 / 1 | 532 / 520 / 9 / 2 / 1 |
| pb_doc_studio_hiring | 20 / 20 / 0 / 0 / 0 | 20 / 20 / 0 / 0 / 0 |
| pb_learn | 422 / 413 / 4 / 1 / 4 | 422 / 413 / 4 / 1 / 4 |
| pb_pay_builder | New | 45 / 44 / 0 / 0 / 1 |
| pb_pay_builder_change | New | 6 / 6 / 0 / 0 / 0 |

| Phase | Numbered cases | Full suites at the phase boundary |
|---|---|---|
| P1 | T1–T34. T18 used the allowed timing skip. Additional tests exercised the real pay reader. | 779 / 765 / 10 / 1 / 3 |
| P2 | T35–T42 passed, including both directions of the live-scheme change. | 605 / 591 / 10 / 1 / 3 |
| P3 | T43–T50 passed, including both letter renderers and approval of an actual hire. | 303 / 301 / 0 / 2 / 0 |
| P4 | T51–T62 passed. T57 included a separate installation with both builder modules absent. An additional signed-offer fallback case passed. | 230 / 225 / 1 / 2 / 2 |

**Final suite totals.** 1,970 cases across eleven modules, 1,931 passed, 24 failed, 6 errored and 9 skipped. All failures and errors match the named baselines. Add employee passed every case in both its combined and final standalone suites. The standalone run used the final language catalogues.

**T18 performance.** The 400-visible-line fixture took 295 ms in the final P1 suite, 325 ms in P2, 322 ms in P4 and 321 ms in P5. The existing mandatory totals operation alone took 133, 146, 150 and 141 ms in those runs. Other warm quotes ranged from 290 to 526 ms. The 60 ms acceptance target was missed on this machine. The timing case is reported as skipped. On the browser fixture the screen initially showed twelve rows and could expand to 399.

**Original seven-suite baseline exceptions**

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

**Additional Learn baseline exceptions**

The final Learn suite reproduced the five original exceptions with identical assertion details. Its scenario check caught a second use of the lesson-advance matcher in the practice example. The final implementation uses the existing input normalizer for matching the example wage, leaving scenario advancement in one place.

- Failure — `test_anchor_registry.TestAnchorRegistry.test_05_no_stray_anchors`
- Error — `test_composer.TestComposer.test_03b_the_source_order_in_ask_is_retrieval_then_column_then_compose`
- Failure — `test_guide_truth.TestGuideTruth.test_02_files_say_what_the_code_says`
- Failure — `test_guide_truth.TestGuideTruth.test_02b_practice_copies_say_what_the_screens_say`
- Failure — `test_learnrev_p4.TestLearnrevP4.test_c1_practice_copies_say_what_the_screens_say`

**Chrome JavaScript suites.** Pay Builder’s formatter passed its eight assertions in one test. Formula Studio ran 179 browser tests on both the pre-feature release and this branch. Each run passed 161 and failed the same 18. Their names follow.

- `@pb_formula_studio/config_loading/closing the initial picker loads a workspace before dismissing it`
- `@pb_formula_studio/config_loading/refreshing the same payroll after a save keeps the workspace visible`
- `@pb_formula_studio/config_loading/switching from Vietnam hides its payroll until Indonesia and its graph are ready`
- `@pb_formula_studio/mapping_canvas/J5 — MF33: Enter on a node is the BUTTON's, never the board's as well`
- `@pb_formula_studio/mapping_canvas/J5 — a dimmed connector is present, not hidden`
- `@pb_formula_studio/mapping_canvas/J5 — a door names a mode, and optionally a connector and a feed`
- `@pb_formula_studio/mapping_canvas/J5 — a ghost is styled as an invitation and still carries its door`
- `@pb_formula_studio/mapping_canvas/J5 — a node id is unique across the WHOLE board, not per lane`
- `@pb_formula_studio/mapping_canvas/J5 — an unmatched lane empties rather than pretending`
- `@pb_formula_studio/mapping_canvas/J5 — the component picture partitions the scheme`
- `@pb_formula_studio/mapping_canvas/J5 — the filter matches THROUGH a neighbour, in both directions`
- `@pb_formula_studio/mapping_canvas/J5 — the five lanes are in story order, and the order IS the story`
- `@pb_formula_studio/mapping_canvas/J5 — the focused node is the one the ring is on, and Escape clears it`
- `@pb_formula_studio/mapping_canvas/J5 — the lane count describes the VIEW, not the board`
- `@pb_formula_studio/mapping_canvas/J5 — the run buckets are the SERVER's four, never invented here`
- `@pb_formula_studio/mapping_canvas/expected, computed and drift are three different sentences`
- `@pb_formula_studio/mapping_categories/Payroll uses the same show/hide model as other category pills`
- `@pb_formula_studio/payslip_table_tools/cells merge downward and split back into the following row`

## 3. Decisions and deviations

- The approved annual scheme has a hidden wage-mapped line with no effect on take-home. The original written headline order would have presented Monthly wage. The owner approved Annual fixed pay as the first box for this scheme. An explicit headline setting wins. Without one, the builder checks which input drives the month. The monthly contract wage is the agreed annual fixed amount divided by twelve.
- On teams without a matching scheme, the old hire preview and automatic contract creation could omit the usual contract amounts of HR’s selected scheme. A narrow hire-context change gives the existing fill that personal scheme and its applicable advance. Old approvals without a personal selection keep their established fallback. The separate payment-run reader and automatic-fill method were left intact.
- The optional `pb_pay_builder_change` module supplies the Change job integration so a standalone Contracts installation keeps its existing dependencies. Its optional button is absent when that bridge is absent. The public joining view renders prepared values with its existing server template framework. Its permissions and data projection are tested independently.
- Document Studio has its own offer-letter table. Both renderers needed the same pay wording. The local machine lacked a server PDF converter. Chrome printed the actual letter to a DEMO PDF for the local signed-copy walk. The release host has wkhtmltopdf 0.12.6.1 with patched Qt.
- Formula Studio’s Health tab used to require read access to accounting journals just to open scheme settings. Accounting choices are loaded only when the manager can read them. Saving the source toggle omits unchanged money fields from the editor payload so governance still applies when money fields genuinely change.
- Practice lessons support English and Vietnamese as specified. The practice month is a fixed example verified using the real compiled engine. Editing away from its wage hides the example. Product screens have English, Vietnamese and Indonesian.
- Test screenshots were saved at the paths in section 5, compared with the prototype and removed according to the repository’s screenshot-retention rule. Section 2 records the unresolved performance target.

## 4. Facts verified

| Question marked unverified in the facts pack | Answer and evidence |
|---|---|
| Is the India scheme active, and does it have a wage mapping? | The live read-only scheme query showed an active scheme and a wage mapping. Its mapped component is hidden and does not feed take-home. A synthetic scheme of the same shape reproduced the result. |
| Does the annual amount have the per-person flag and a usual amount? | The annual fixed amount is a per-person money input. Its usual value is zero and it drives take-home. On the old hire path the synthetic scheme paid only the independently supplied allowances, ₹1,050 net. |
| Which signed-offer contract writer runs? Are amounts imported twice? | The installed Add employee override returned the studio contract before the older package importer. A rolled-back probe counted zero calls to the older writer. T50 approved a real local hire and found exactly one contract amount per entered code, including an explicit zero. This resolves both occurrences of the override question. |
| Does the existing contract approval detail understand dictionary-shaped component changes? | The existing formatter raised `KeyError` on a synthetic proposal of that shape. Its existing inbox wrapper returned `None`. This was reproduced locally. The dated pay-change route uses Change job and passed the inbox walk. |
| Which existing scheme takes priority on a real pay run? | The deployed ordinary-pay resolver matched `5a31a6fcf`. A dated work segment with an explicit scheme applies for that period. Otherwise the person’s active assignment wins and the team supplies a fallback. Advances and final settlements retain their separate rules. On an unassigned team and a conflicting team, the new quote, payslip preview and actual payroll all agreed on ₫25,952,500. |
| What installation dependencies change? | Add employee already brings Formula Studio, the engine, import kit and scheme map. The shared module additionally uses the existing Pay module, installed on all five targets. The optional contract bridge isolates Change job and its organisation-chart dependency. No new server packages or standard modules were introduced. |

## 5. Browser walks and design assessment

Chrome opened all four prototype homes with both schemes. The local product walks used DEMO records and Chrome with the console open. Product captures below were taken under `docs/handovers/paybuilder/shots/`.

| Walk | Observed result | Captures before cleanup |
|---|---|---|
| W1, monthly Add employee | ₫30,000,000 wage produced ₫30,730,000 gross, ₫4,777,500 deductions, ₫25,952,500 take-home and ₫6,450,000 company contributions. The right-hand payslip agreed. Changing, resetting and adding allowances, temporary overtime, three explanations, progressive tax, summary and the real approval inbox were exercised. The phone amount entered by HR appeared on the proposal. | `p1-{locale}-{width}.png` |
| W2, yearly and exceptional cases | ₹12,00,000 annual fixed pay showed ₹1,00,000 a month before deductions. The real breakdown was ₹98,250 gross, ₹3,200 deductions, ₹95,050 take-home and ₹3,000 company contributions. Working back from ₹1,00,000 returned ₹12,60,000 yearly and ₹1,00,050 take-home. The chip in Basic’s explanation focused the annual input. Checked missing net, broken formula, no scheme, wage-only, file-only, insufficient access, plan limit, slow load and retry. | `p1-annual-comparison.png`, `p1-annual-{width}.png` |
| W3, Formula Studio | A manager without journal access opened scheme settings. Changing the source in each direction displayed the headcount, names, Keep and confirmation. A saved Year reopened correctly. English, Vietnamese and Indonesian passed keyboard and width checks. | `p2-warning-{locale}.png` |
| W4, Hiring | A ₫30,000,000 offer with lunch and a ₫500,000 phone allowance produced ₫31,230,000 gross and ₫26,377,500 take-home. Itemised and gross-only letters rendered. The candidate accepted, HR recorded the signed copy, and Add employee displayed the wage and phone amount as coming from the signed offer. Temporary overtime stayed out of the letter and contract. All three languages passed. | `p3-letter-{locale}.png` |
| W5, Contracts | A monthly change from ₫30,000,000 to ₫31,000,000 showed a ₫800,000 take-home gain. A second user approved it. Advancing the local scheduled job to the effective date applied it once and added it to History. The restricted role had no Change pay button. On a standalone Contracts install, both Terms and Components opened without that button or a console error. | `P4-{locale}-change.png` |
| W6, layout and keyboard | Add employee fit 1440, 1180, 820, 600 and 400 px in all three languages with reduced motion. Normal motion was exercised on the annual case. Enter, Escape, refocus through a chip and navigating to a folded line worked. Slow responses retained the last result and current input. | `p1-{locale}-{width}.png` |
| W7, employee joining | At 360 × 740 px the joiner entered their code and opened Your pay. Keyboard Enter disclosed Basic’s sum. This contract’s insurance answer was zero. Take-home was ₫27,850,000 in each of the three languages. Public output showed the employee’s earnings and deductions. | `P4-{locale}-joining.png` |
| W8, live | Pending release. | Pending |

The Learn practice card showed ₫10,230,000 gross, ₫997,500 in deductions and ₫9,232,500 take-home after entering ₫9,500,000. A different wage hid that fixed example. Checked in English and Vietnamese with the keyboard and reduced motion. Captures were taken as `P5-practice-{en_US,vi_VN}.png`.

Side-by-side comparisons led to a 26 px headline, a 38 × 22 px offer-letter switch, the person’s name in the contract dialog, and line-kind icons and disclosure arrows on the phone. A formative check of the approved design earns **8/10**. Entering one amount, following an explanation and returning to its source worked across the four homes. The failure, loading, no-scheme and restricted states offered a clear action or explanation. The largest scheme exceeded its response-time target. Comparative user testing against other products has not been conducted. The practice card’s final English and Vietnamese runs also checked that the row values lined up separately from their names.

## 6. Release and verification

Local release checks passed apart from the stated timing target and the original suite exceptions. Production results will be recorded after the release script runs. The five targets are payobook, payobook_template, p0clone, rize and sudima.

## 7. Ledger additions

D10 records the yearly headline, D11 the person’s scheme priority and D12 the five-database release scope including Sudima. PB19–PB23 cover hidden informational wage mappings, real-contract fill, timing, multiple schemes and keyboard focus on folded lines. PB24–PB27 record the Studio save payload, optional accounting rights, the two letter renderers and the single signed-offer importer. PB28–PB31 record the main-cycle scheme on existing contracts, keyboard ownership in a nested dialog, standalone Contracts installations and pasted amount grouping. PB32 records the lesson’s authoring and example amount.

## 8. Questions for the owner

**Already decided.** On the annual scheme, HR enters ₹12,00,000 once in **Annual fixed pay**. The contract shows ₹1,00,000 a month before deductions. A new company sees the first amount its selected scheme uses. A monthly scheme opens with **Monthly wage**. If the company has no scheme yet, HR can enter the wage and the screen explains why it cannot show the breakdown.

Two choices for a future change remain open. The current release follows the approved behaviour.

- Should a second person approve when a manager changes a live allowance from a monthly entry to an amount kept on each person’s contract, or the other way round? Today the manager sees the headcount and can confirm the change.
- Should Hiring keep **Build from a total** alongside the new Pay Builder? Both are available in this version.
