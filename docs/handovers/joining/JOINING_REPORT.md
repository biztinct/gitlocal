# Joining portal build report

## 1. What was built

The isolated branch is `joining`. It starts from `c4564f127`. The release utility was brought across in `e7c38a944` and the approved design pack was committed first in `7e9a6a726`.

| Phase | Commit | Outcome |
|---|---|---|
| P1 | `f00196647` | A signed offer creates a private phone link. The joiner opens it with a code, saves details and papers, and sends them to HR. |
| P2 | `6ad7905f3` | Hiring and People share the Joining board. HR can invite, check, accept, send back or cancel. Eligible recruiters can pass on a link and code. |
| P3 | `b06b9f112` | Joiners sign company papers. Add employee opens with checked answers and files the documents through its existing hire and approval process. |
| P4 | `3e220ee95` | A daily job sends reminders, nudges HR and erases private staging data after 30 days. The phone, board, messages and signing screens have English, Vietnamese and Indonesian wording. The release utility protects Joining links and preserves scheduled jobs. |

## 2. Tests before and after

The baseline was recorded before changing the modules, on local database copies aligned with the fetched code. Six Hiring public-page checks initially returned HTTP 404 when the local database filter matched two copies. All six passed on the same code with the exact database name. The baseline below includes that rerun.

| Module | Before, passed / run | After, passed / run |
|---|---:|---:|
| Joining | New module | 72 / 72 |
| Hiring | 521 / 532 | 521 / 532 |
| Add employee | 178 / 178 | 178 / 178 |
| Onboarding | 20 / 20 | 20 / 20 |
| People hub | 25 / 27 | 25 / 27 |

Joining passed 29 tests at P1, 51 at P2 and 63 at P3. P4 includes all numbered checks T1–T70. Some test methods cover more than one numbered check, and additional methods cover recovery after failures. The four-country comparison created pairs of employees in Vietnam, Indonesia, India and Singapore and checked the employee fields against the equivalent manually typed hire. The final Hiring and People hub failure names matched their baselines exactly. A separate test verified the HR sender as bank proposer. A temporary vault failure left the employee uncreated, preserved the approved request and allowed that same request to succeed on retry.

The signed-PDF test merged a real original and signing confirmation. A separate inspection found the paper title, signer, original fingerprint and embedded signature on the rendered confirmation. All 486 exported terms have Vietnamese and Indonesian translations.

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

## 3. Design decisions and changes to Add employee

- **HR and recruiters.** The person handling a particular offer and HR can both show a code, as the owner decided. Either can open the joiner's phone page with the link and code. Recruiters see item names and states only in the board drawer.
- **Returning phones.** All five sites use seven-day inactive staff sessions. A successful code also issues a signed, host-only Joining cookie, limited to that link. It restores access until 14 days from verification. The owner approved this separate cookie.
- **Signing.** The production server has the PDF writer but no PDF page renderer. The phone uses the approved **Open the paper** option. Opening the original, agreeing, entering a name and drawing a signature are required. Signed policies are filed in **Labor Contract**. The owner approved **Identity card — no end date** for permanent cards, with the same access as the ID folder.
- **Offer automation.** The switch is under **Papers to sign** on Joining. Hiring declares its built-in switches in a fixed list. The signed-offer trigger and message delivery were built during P1 so T1–T4 could exercise the real path.
- **Company-required fields.** A checked hire opens on **Check and add** when ready. If the company requires another answer, such as a shuttle route, Add employee opens on that step.
- **Existing access.** Bringing the signed wage across uses Hiring's existing offer access. An HR user who can add an employee but cannot read that offer sees a message identifying who can finish. The existing employee workspace separately requires contract-reading rights to show the completed record.
- **Release tooling.** The owner approved a correction that restores every previous scheduled job's own setting while keeping the new Joining job active. The wrapper now stages the named custom module from its actual directory at the committed revision, reads the standard-addon list as the checkout owner and preserves the release author's name across SSH. The owner also approved redacting Joining links on the active websites.

Add employee changed from `19.0.1.8.1` to `19.0.1.8.2`. The following are its only source edits.

| File | Change |
|---|---|
| `pb_new_hire/models/studio.py` | Exposed the draft field allowlist through `_draft_keys()`. |
| `pb_new_hire/models/studio_welcome.py` | Used the same hook when saving and restoring a draft. |
| `pb_new_hire/models/welcome_legs.py` | Exposed the order of the existing post-approval steps through `_leg_order()`. |
| `pb_new_hire/static/src/js/studio_util.js` | Allowed an additional document choice to count as already received in the existing progress tally. |
| `pb_new_hire/static/src/js/step_check.js` | Read the extended document choice when listing received information and explaining the bank approval. |
| `pb_new_hire/static/src/js/record_panel.js` | Used the same choice when describing whether the account is ready for a second person to approve. |

## 4. Chrome walks

The local walks used Chrome with the console monitored. Each listed walk finished with zero console errors. All five approved prototype tabs were opened before implementation. Capture paths below are relative to this report. The 40 local test screenshots were removed after review as required by the repository’s cleanup instructions.

| Walk | Observed result | Captures under `shots/` |
|---|---|---|
| W1 | At 360 × 740 the joiner saved all sections, uploaded papers, signed two policies, reused a signature and sent. Vietnamese and Indonesian both showed the code, welcome and sections screens. | `prototype-phone.png`, `w1-en_US-{code,welcome,hub,personal,id_number,bank,tax,emergency,papers,day,sent}.png`, `w1-{vi_VN,id_ID}-{code,welcome,hub}.png`, `w1-sign-paper.png`, `w1-signed-list.png` |
| W2 | HR opened Joining in both hubs, searched, filtered, checked items, showed a code, invited someone, edited first-day details and saved company papers. | `w2-{hiring-board,people-board,hr-drawer,invite,what-is-asked,paper-settings}.png` |
| W3 | The recruiter saw progress without private values or files. An ordinary colleague had no Joining tab. | `w3-{recruiter,plain}.png` |
| W4 | A recorded signed offer became an employee through Add employee. Seven documents were filed, including two signed policies. The employee appeared in Ready for day one and the bank request waited for a second person. An HR colleague with existing contract access opened the employee document list and saw both policies. | `w4-{check-and-add,studio-details,added,employee-documents,employee-workspace,day-one}.png` |
| W5 | HR sent a tax number back. The phone reopened that section, the joiner changed the masked number and resubmitted, and HR accepted it. | `w5-hr-return.png` |
| W6 | The board and drawer fitted 1180, 820 and 600 pixels. The phone fitted 320 and 480 pixels. | `w6-board-{1180,820,600}.png`, `w6-phone-{320,480}.png` |

## 5. Release and live proof

The risky release returned `OK` on November 27, 2026. Both branches contained release commit `d7db27c7a3ce21f58b5fe91a591cd871e83e374c`. The script used the verified nightly backups for all five databases. It recorded 109 seconds of downtime and 125 seconds overall. The server log is `/tmp/pbrel-20261127-090407-41182/run.log`.

| Target | Joining | Add employee | Active jobs before → after | Login after release |
|---|---|---|---|---|
| payobook | 19.0.1.0.0 | 19.0.1.8.2 | 60 → 61 | Public 200 |
| payobook_template | 19.0.1.0.0 | 19.0.1.8.2 | 41 → 42 | Public 404, internal 200 |
| p0clone | 19.0.1.0.0 | 19.0.1.8.2 | 50 → 51 | Public 200 |
| rize | 19.0.1.0.0 | 19.0.1.8.2 | 93 → 94 | Public 200 |
| sudima | 19.0.1.0.0 | 19.0.1.8.2 | 92 → 93 | Public 200 |

An independent check matched both installed module trees to the committed files by SHA-256. The new daily job was active in every database. The server log and all five upgrade logs contained zero errors or tracebacks during verification. Two rounds of HTTP checks confirmed redaction of request paths and referrers across all 17 configured listeners. The owner confirmed the private template behavior and the successful retry of the previous Rize operation.

Seven isolated release tests passed. A separate PostgreSQL rehearsal preserved all existing job settings and new job defaults. Immediately before deployment, Chrome repeated the three-language phone flow, both boards, send-back, signing, and Add employee. The employee had seven filed documents, two signed policies and a bank account awaiting independent review. These walks had zero console errors. The 37 screenshots from this repeat were reviewed and removed.

The following NOTE was appended to `/opt/deploy-notes.md` and read back after independent verification.

> 2026-11-27 09:07 UTC | Codex JOINING | NOTE | pb_joining,pb_new_hire | payobook,payobook_template,p0clone,rize,sudima | Verified d7db27c7a: both module trees match the commit by SHA-256. Versions 19.0.1.0.0 and 19.0.1.8.2 on all five. Active jobs 60→61, 41→42, 50→51, 93→94, 92→93. Joining daily job active on all five. Four public logins 200. Template public 404 and database-specific internal 200 as approved. Zero ERROR/CRITICAL/Traceback in the server and five upgrade logs since release start. Redaction confirmed in 34 request and referrer records across 17 configured listeners. Release OK, 109s down.

**Live Chrome proof.** The Payobook phone page for an inactive link displayed “This link is not active” and “Ask the person who sent it for a new one.” Chrome reported zero console errors. The Payobook, Rize and Sudima sites showed their sign-in pages. The authenticated demo hire on Payobook and the read-only Joining board checks on Rize and Sudima are awaiting the owner’s sign-in. No demonstration records have been created on the live databases.

## 6. New ledger entries

J-1 through J-5 cover the isolated test database, recruiter access, scheduled jobs, module staging and access logs. J-6 through J-10 cover permanent cards, PDF display, mobile layout, remembered devices and private page rendering. J-11 through J-13 cover the board's initial filters, drawer updates and language-specific messages. J-14 through J-18 cover approval timing, filing recovery, ID document dates, company-required fields and PDF verification. J-19 records how to verify the server's standard-addon list. J-20 through J-22 cover the private template, successful retries and validation of each active website listener.

## 7. Open owner question

Should HR who can review someone in Joining also be allowed to bring across the signed wage when Hiring has not given them access to that offer? The implementation preserves the existing access rule.

## 8. Learn lessons for a later edit

- L39, “Work a role's board, from applied to joined”, should point from recording a signed offer to Hiring › Joining.
- L17, “Get ready for someone starting”, should explain when to use Joining before day one and when the employee first appears in Joiners.
- L29, “Employees and their contracts”, should mention that a checked Joining record opens Add employee with the information HR has accepted.
