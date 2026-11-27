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
