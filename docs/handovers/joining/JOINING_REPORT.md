# Joining portal build report

## 1. Work by phase

The approved design pack is on branch `joining` at `7e9a6a726`. The base is `c4564f127`. The release utility was brought across in `e7c38a944`.

## 2. Test baseline

Measured before adding the new module, using local copies of the test database with custom modules upgraded to the fetched code.

| Suite | Tests before | Passed before | Failed before | After |
|---|---:|---:|---:|---|
| Hiring | 532 | 521 | 11 | Pending |
| Add employee | 178 | 178 | 0 | Pending |
| Onboarding | 20 | 20 | 0 | Pending |
| People hub | 27 | 25 | 2 | Pending |

Six additional Hiring application-page tests initially returned HTTP 404 with an ambiguous local database filter. All six passed on the same code when rerun on the isolated database with its exact name. The table includes that rerun.

### Existing failures

- `pb_people_hub.test_people_hub.TestPeopleHubStatic.test_the_contracts_action_opens_the_board_with_a_way_back`
- `pb_people_hub.test_people_hub.TestPeopleHubStatic.test_the_lens_order_matches_the_mockup`
- `pb_hiring.test_client_review.TestClientReview.test_hiring_only_cannot_read_access_directory`
- `pb_hiring.test_interviews_p5.TestRecruitInterviewsP5.test_07b_without_google_nothing_changes`
- `pb_hiring.test_joining_p6.TestRecruitJoining.test_11_the_numbers_filters_funnel_ageing_leadership_and_exports`
- `pb_hiring.test_offer.TestTheCover.test_t7_who_is_asked_to_agree_it_is_said_out_loud`
- `pb_hiring.test_privacy_p4.TestRecruitPrivacy.test_02_the_manager_sees_the_card_and_a_sentence_until_shared`
- `pb_hiring.test_privacy_p4.TestRecruitPrivacy.test_02b_unsharing_regenerates_the_file_tokens`
- `pb_hiring.test_privacy_p4.TestRecruitPrivacy.test_08_the_resume_bank`
- `pb_hiring.test_privacy_p4.TestRecruitPrivacyFiles.test_02_tokenised_cv_link`
- `pb_hiring.test_registers_p9.TestRegistersP9.test_06_the_overview_tiles_equal_the_register_counts`
- `pb_hiring.test_registers_p9.TestRegistersP9.test_08_the_hub_names_the_two_registers_between_overview_and_interviews`
- `pb_hiring.test_stages_p1.TestRecruitStages.test_13_set_up_has_six_cards_and_none_is_a_dead_end`

### Phase 1 local proof

All 29 Joining tests passed, including T1–T22 and checks for device confirmation, rate limits, private drafts and file limits. The signed-offer trigger and message delivery were implemented in P1 because T1–T4 and the code flow exercise them. Existing module files have no P1 edits.

At 360 × 740, Chrome completed the English journey from the code to “Sent to HR”, including uploading papers, leaving the bank account until later, and leaving and returning to a draft. Chrome opened the code, welcome and section-list screens in Vietnamese and Indonesian. All three walks finished with zero console errors. The application access log showed 44 redacted Joining requests and zero unredacted Joining URLs. The comparison image was `shots/prototype-phone.png`. Walk captures used `shots/w1-en_US-{code,welcome,hub,personal,id_number,bank,tax,emergency,papers,day,sent}.png` and `shots/w1-{vi_VN,id_ID}-{code,welcome,hub}.png`.

### Phase 2 local proof

Phase 1 was pushed in `f00196647`. The board now opens immediately after Offers in Hiring and immediately before Joiners in People. The five figures, step and search filters, invitation, first-day editor, private file viewer, review actions, and the command palette use the existing hub and filter components. The offer automation setting is in Joining settings because Hiring defines its built-ins as a fixed list. The same message template and sender handle direct invites and signed offers, including emails with Vietnamese and Indonesian wording.

All 51 tests in the complete Joining suite passed (29 from phase 1 and the 22 numbered board checks, T23–T44). No existing module was edited in this phase. Chrome at 1440px completed W2 in both hubs and opened Add employee's existing country paper editor. W3 confirmed the recruiter received names and item states only and an ordinary colleague had no Joining tab. W5 returned a tax number to the phone, changed the masked value, resubmitted it, and accepted it on the board. The console was clean in all three walks. Captures used `shots/w2-{hiring-board,people-board,hr-drawer,invite,what-is-asked}.png`, `shots/w3-{recruiter,plain}.png` and `shots/w5-hr-return.png`. Company paper setup and the Add as employee action are scheduled for phase 3.

### Phase 3 local proof

Phase 2 was pushed in `6ad7905f3`. HR can choose an accepted item in Add employee, switch to typing it, or ask the person for it later. The server reads accepted values from the joining when HR sends the hire. The existing approval route and bank proposer are preserved. A withdrawn or rejected hire becomes available to HR again.

Company papers can be switched on for everyone or for one country. The phone uses **Open the paper** because the server has no PDF page renderer. After the person opens it, they can agree, draw their signature and sign. The filed PDF contains the original pages and a signing confirmation with the document fingerprint. Signed copies go to the existing **Labor Contract** category. Permanent cards go to **Identity card — no end date**, with the same document access as other ID cards.

The changes inside Add employee were confined to the draft, approval and document-summary extension points and their callers, plus the version increase from `19.0.1.8.1` to `19.0.1.8.2`.

| File | Change |
|---|---|
| `pb_new_hire/models/studio.py` | Exposed the draft field allowlist through `_draft_keys()`. |
| `pb_new_hire/models/studio_welcome.py` | Used the same hook when saving and restoring a draft. |
| `pb_new_hire/models/welcome_legs.py` | Exposed the order of the existing post-approval steps through `_leg_order()`. |
| `pb_new_hire/static/src/js/studio_util.js` | Allowed an additional document choice to count as already received in the existing progress tally. |
| `pb_new_hire/static/src/js/step_check.js` | Read the extended document choice when listing received information and explaining the bank approval. |
| `pb_new_hire/static/src/js/record_panel.js` | Used the same choice when describing whether the account is ready for a second person to approve. |

The four-country comparison runs two real hires per country and checks the employee fields supplied by each catalogue. A separate test verifies that a bank account waits for a second person and names the HR sender as proposer.

Chrome found a company-required shuttle-route field. Joining loads the company's Welcome options before choosing the first step, so HR sees the missing answer immediately. The studio's summary and bank panel use the same classification as the progress tally.

The Joining suite passed all 63 tests, including a simulated temporary filing failure followed by a successful retry of the same approval. Add employee passed 178 of 178 in its first full P3 regression. The PDF check inspected the rendered page text and embedded images and found the paper title, signer, signing confirmation, original fingerprint and signature image.

### Learn lessons for a later edit

- L39, “Work a role's board, from applied to joined”, should point from recording a signed offer to Hiring › Joining.
- L17, “Get ready for someone starting”, should explain when to use Joining before day one and when the employee first appears in Joiners.
- L29, “Employees and their contracts”, should mention that a checked Joining record opens Add employee with the information HR has accepted.

Chrome completed the full W4 journey from a signed offer to a ready-for-day-one employee. The demo employee received seven documents, including two policies signed on the phone. The bank request was waiting for HR review. An HR colleague with existing contract-reading rights opened both signed policies in the employee document list. The narrower HR test account could add the employee but the existing employee workspace required contract-reading rights to display the record.

W1 covered two policy signatures, including reusing the first signature. W2 covered company paper setup. W6 checked the board and drawer at 1180, 820 and 600 pixels and the phone at 320 and 480 pixels. All walks finished with zero Chrome console errors. Captures used `shots/w1-sign-paper.png`, `shots/w1-signed-list.png`, `shots/w2-paper-settings.png`, `shots/w4-{check-and-add,studio-details,added,employee-documents,day-one}.png`, `shots/w6-board-{1180,820,600}.png` and `shots/w6-phone-{320,480}.png`.

After the document-summary change, the complete Add employee suite passed again, 178 of 178.
