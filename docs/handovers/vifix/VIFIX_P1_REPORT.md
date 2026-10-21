# VIFIX P1 — audit report (Opus, 2026-10-21)

Scope: handover `VIFIX_P1_HANDOVER.md` A–F. Branch `vifix-p1` from 19.1 `f4b3b9492`. **Audit only: no product
.po, template or JS changed, nothing deployed, nothing pushed, abm untouched.** Tools in `docs/handovers/vifix/tools/`,
baseline outputs (2026-10-21) in `docs/handovers/vifix/p1_out/`, screenshots in the session scratchpad
`/private/tmp/claude-502/-Users-adity-Documents-GitHub-gitlocal/d3a7939f-6b40-427b-9e7d-c5a89b5a6ab8/scratchpad/sweep/full4/shots/`.

## In one paragraph
Payobook's Vietnamese is not missing; it is **stale, dropped or machine-made**. 0 entries are empty, yet 7,707
user-facing strings in installed modules never reach a Vietnamese screen (3,197 Python messages were never added to their
module's file, 1,693 template texts have no translation anywhere, 612 JS strings are not wrapped for translation, 227
translated entries are silently dropped by a stale `.pot`, 316 never load for a missing marker). On top of that, 1,230
existing translations read wrong (word-for-word word order, literal machine words such as "cú đấm", "thợ mộc", "phòng
cấm", "sân khấu", "ống kính", mixed English). The live sweep confirms it: **106 of 108 screens** still show English to a
Vietnamese user. The fix is about 70 working days if everything is done; the screens most people see (Home, approvals,
running payroll) are about 14 days.

## Tests
| Test | Result |
|---|---|
| T1 offline, < 5 min, deterministic | **pass.** Two runs each, byte-identical: po scan 7 s, literal scan 15 s, glossary 2 s, wave plan < 1 s, replica drift 60 s. The committed glossary equals a fresh build. |
| T2 finds the known bad examples | **pass.** "Thiếu cú đấm" (pb_close:324, pb_mission:377), "Hết tiền" (pb_pay_delivery:483, pb_approval_config:1665), and the Lifecycle boards: 177 template texts with no Vietnamese (Contracts 37, Probation 66, Exits 49, Joiners 25), more than the ~80 expected. |
| T3 live sweep covers every sidebar entry and hub tab | **pass.** All 11 rail entries and all 65 hub tabs (the full list read from the app's own tab-gate registry), 30 Settings cards, 3 inbox sub-tabs, 10 detail drawers. 0 skipped, 0 console errors. Four tabs the QA user cannot see were opened by granting groups **on the clone only** (VF9). Not covered: see "Not visited" below. |

## A. Static .po scan (`tools/vifix_po_scan.py`)
138 modules in scope (pb_, biz_, biztinct_, minus standard addons), 124 with `vi_VN.po`, **27,005 effective entries**
after the `.pot` merge (the server's exact reading, VF2). 14 without a `.po`: biz_approval_chain, biz_audit_trail,
biz_debrand, biz_deroute, biz_deroute_website, biz_doc_ocr, biz_geo_tracking, biz_host_db, biz_mail_debrand,
biz_week_grid, biztinct_website, pb_me_portal_website, pb_payroll_mapping_vn, pb_payroll_templates (the last one has 438
untranslated strings in scan B).

| Check | Findings | In installed modules | Modules | Top modules |
|---|---|---|---|---|
| same_text (msgstr = English, minus allowlist) | 68 | 62 | 17 | pb_formula_studio 15, pb_hr_payroll_analytics 9, pb_hr_payroll_base 8 |
| empty | 0 | 0 | 0 | — |
| pot_dropped (translated but never loaded, VF2) | 227 | 227 | 5 | pb_approval_config 89, pb_pay 45, pb_group 44, pb_budget 27, pb_scheme_map 22 |
| suspicious (seed list, 47 seeds) | 261 | 252 | 50 | pb_hr_payroll_formula, pb_formula_studio, pb_attendance_flow, pb_hr_payroll_analytics |
| word_order (English Title Case kept, VF7) | 388 | 373 | 30 | pb_hr_payroll_base 121, pb_hr_payroll_formula 88, pb_hr_payroll_analytics 68 |
| mixed (English word inside Vietnamese) | 638 | 616 | 61 | pb_hr_payroll_base 183, pb_hr_payroll_formula 78, pb_hr_payroll_analytics 61 |
| no_diacritics | 5 | 4 | 5 | all five reviewed: false positives (real toneless words) |
| loanwords (email, file, demo…: for the glossary, not errors) | 375 | 372 | 43 | pb_hiring 184, biz_access 47 |
| markers (never load, VF5) | 442 | 316 | 25 | biz_approval_workflow 74, biz_access 37, legacy country modules |
| placeholders (would crash or garble) | 4 | 4 | 2 | pb_comp_ben (`%(month)s` vs `%(num)s`, 3), pb_decision_room (stray %) |
| terminology drift (one English, several Vietnamese) | 568 msgids | | | "People" ×5 variants, "Created on" ×5, "Pay run" (Đợt lương / Kỳ lương), "Department" (Phòng ban / **Phòng cấm**) |

No "Odoo" in any msgstr or English msgid of our modules. Full lists: `p1_out/po_scan.md` (first 40 per check) or
`python3 tools/vifix_po_scan.py --json out.json` (every row with file:line, English, current Vietnamese).

Worst literal translations found (each is a seed now): "Thêm một cú đấm" (punch = a blow), "thợ mộc" (joiner = carpenter),
"Phòng cấm" (department = forbidden room), "mạng lưới" (net = network), "cai trị" (rule = to govern), "tiến lên"
(advance = move forward), "Xuất khẩu" (export = trade export), "Nhận phòng / Trả phòng" (check-in/out = hotel room),
"Thuật sĩ" (wizard = sorcerer), "buồng lái" (cockpit), "Chạy song song bóng" (shadow run), "Diễn viên hàng đầu" (top
actors), "Tháng Tăng Lão Đồng" (Lao Động read as "old man, copper"), "Phông chữ tuyệt vời" (Font Awesome translated).

## B. Unextracted / untranslated literals (`tools/vifix_literal_scan.py`)
Coverage follows the server's lookup rules (VF3): JS = own module, then any loaded module incl. standard addons; Python =
own module only. pb_learn left out (LEARNREV). **7,927 findings, 7,707 in installed modules.**

| Class | What it means | Findings | Installed | Modules |
|---|---|---|---|---|
| xml_text | template text with no Vietnamese anywhere | 1,693 | 1,693 | 42 |
| xml_attr | tooltip/placeholder/aria label with no Vietnamese | 249 | 249 | 34 |
| xml_expr | English inside a template expression (`t-esc="x ? 'Saving…' : 'Save'"`): **needs code** | 521 | 520 | 55 |
| js_unwrapped | JS string shown on screen, not in `_t()`: **needs code** | 662 | 612 | 47 |
| js_wrapped_uncovered | `_t("…")` with no Vietnamese yet | 619 | 619 | 36 |
| js_concat | sentence glued from pieces: **needs code** | 76 | 63 | 21 |
| py_unwrapped | Python UI string (dict label/title/hint…, UserError) not in `_()`: **needs code** | 850 | 754 | 61 |
| py_wrapped_uncovered | `_("…")` missing from its own module's file (VF4) | 3,257 | 3,197 | 66 |

Top modules (installed): pb_tenants 911, pb_goals 604, pb_formula_studio 510, pb_payroll_templates 438, pb_training 397,
pb_hr_payroll_formula 314, pb_probation 274, pb_pip 243, pb_timeoff 236, pb_offboarding 221, pb_assets 211,
pb_contract_lifecycle 195. Full lists: `p1_out/literal_scan.md` (first 60 per class) or the tool's `--json`.
Precision: samples of every class were checked by hand (grep of the `.po`): the wrapped-uncovered and template classes
were real in every sample; js_unwrapped keeps some false positives (short field names passed as data), roughly 1 in 6.

## C. Live Vietnamese sweep
Clone `vifixp1clone` = `pg_dump payobook --exclude-table-data=hr_payslip_line` (restore 84 s), jobs 0 active, AI
connection off, every `*api_key*` blank, mail off, served alone by its own odoo-bin on 127.0.0.1:8077 (no cron
threads) through an ssh tunnel; own headless Chrome on port 9577 with a fresh profile; QA user signed in by fetch,
language vi_VN and default company 5 on the clone only. Reached every screen through the left menu (LR80).
**Dropped at 02:17 UTC** (`dropdb --force`, filestore removed, unit stopped, temp files removed, DONE line in
`/opt/deploy-notes.md`). Databases left: payobook, payobook_template, p0clone, rize.

**108 screens recorded; 106 still show English; 1,338 distinct English or mixed strings (2,120 counted per screen).**
"Records" counts strings not found in our source (people, departments, pay-run names): reported apart, not counted.
Classified rows (product strings only, no record data): `p1_out/live_sweep_rows.json`.

Worst screens: Workforce › Shift schedule 167, Workforce › Time off 73, Home › Inbox › Done 60, Settings › HR › Hiring
setup 57, Settings › Payroll › Formula studio 52, Insights › Training 52, Settings › Company › Your company 45,
People › Joiners 43, People › Exits 43.

Reads wrong on screen (seed list on the visible Vietnamese): "ống kính" (lens) on 27 screens ("Tìm kiếm người, ống kính,
hành động…" in the Workforce search box, "Ống kính lực lượng lao động"), "Sân khấu" (stage) on 21 (the hub header chip
"THG 10 2026 · SÂN KHẤU 2 / 5"), "Hết tiền" on 10, "tiến lên" ("Tháng chỉ tiến lên khi đợt lương chậm nhất tiến lên"),
"Thiếu cú đấm", "Không có ca, đấm hoặc rời đi vào ngày này", "Diễn viên hàng đầu", "Xuất khẩu", "lập bản đồ".
Also seen by eye: the run board says "01 Draft 18 kỳ lương" (English state, and runs counted as "kỳ lương"); English
dates on Vietnamese screens ("Thu 17 Sept", "21 October", "Oct 2026", "thg 10 2026"); pay-run names generated in
English ("Payobook Logistics — End-Month Payroll · October 2026"); the rail section labels "vận hành / Hiểu / Phát
triển" (see open questions); Discuss and the top-bar Payroll app menu ("Employees", "Payslips", "Batch Payslips").

Not visited, and why:
- **My Payobook (the employee pages, `/my`)**: a portal login, not the staff menu this sweep walks. It is the page most
  people see; the literal scan covers its modules (W1) and the next sweep should log in as a demo employee.
- The standard top-bar apps (Discuss, Calendar, CRM…) are outside the Payobook menu; only Discuss was looked at.
- Home › Inbox › "My turn" has no item for the QA user, so no approval card opened from that sub-tab; the other three
  inbox sub-tabs show every card's text inline and were recorded.
- Payslip breakdown lines: the clone leaves out payslip lines (LR16), so a payslip opens without lines.
- Other sessions were allowed to deploy during the sweep (Fable's NOTE at 02:16 UTC); the clone server loaded the code at
  01:35 UTC, so the sweep shows the code of that moment.

Every screen (the "Examples" column shows up to 5; the JSON has all):

| # | Screen (as the menu shows it) | English / mixed | Records | Examples still in English | Reads wrong | Screenshot |
|---|---|---|---|---|---|---|
| 1 | Trang chủ › Tổng quan | 16 | 5 | “Awards run — Oct 2026”; “Biểu đồ cột. Dùng phím mũi tên để đổi tháng, phí”; “Construction”; “Corporate Office”; “Information Technology” | “· Sân khấu” | 001_Trang_chủ_Tổng_quan.png |
| 2 | Trang chủ › Hộp thư | 2 | 1 | “Trang chủ lenses”; “thg 10 2026 — stage 2 of 5” | “Hết tiền”; “· Sân khấu” | 002_Trang_chủ_Hộp_thư.png |
| 3 | Trang chủ › Hộp thư › (detail) | 0 | 0 | — | — |  |
| 4 | Trang chủ › Hộp thư › Tất cả tôi xem được | 19 | 20 | “Approved by an officer”; “Expense claim · Bùi Hữu Khang · 1 receipt”; “Expense claims · b1”; “Experience letter”; “Finance approver” | “Hết tiền”; “· Sân khấu” | 003_Trang_chủ_Hộp_thư_Tất_cả_tôi_xem_được.png |
| 5 | Trang chủ › Hộp thư › Tất cả tôi xem được › (detail) | 19 | 20 | “Approved by an officer”; “Expense claim · Bùi Hữu Khang · 1 receipt”; “Expense claims · b1”; “Experience letter”; “Finance approver” | “Hết tiền”; “· Sân khấu” | 004_Trang_chủ_Hộp_thư_Tất_cả_tôi_xem_được_detail_.png |
| 6 | Trang chủ › Hộp thư › Đã trả lại | 7 | 11 | “Announcement”; “Announcement · b1”; “Goal sheet”; “HR lead”; “Their manager” | “Hết tiền”; “· Sân khấu” | 005_Trang_chủ_Hộp_thư_Đã_trả_lại.png |
| 7 | Trang chủ › Hộp thư › Đã trả lại › (detail) | 7 | 11 | “Announcement”; “Announcement · b1”; “Goal sheet”; “HR lead”; “Their manager” | “Hết tiền”; “· Sân khấu” | 006_Trang_chủ_Hộp_thư_Đã_trả_lại_detail_.png |
| 8 | Trang chủ › Hộp thư › Đã xong | 60 | 117 | “Add an expense to a budget”; “Announcement”; “Announcement · b1”; “Approved by an officer”; “Approved by the manager” | “Hết tiền”; “· Sân khấu” | 007_Trang_chủ_Hộp_thư_Đã_xong.png |
| 9 | Trang chủ › Hộp thư › Đã xong › (detail) | 60 | 117 | “Add an expense to a budget”; “Announcement”; “Announcement · b1”; “Approved by an officer”; “Approved by the manager” | “Hết tiền”; “· Sân khấu” | 008_Trang_chủ_Hộp_thư_Đã_xong_detail_.png |
| 10 | Trang chủ › Hỏi Nhân sự | 3 | 6 | “Home”; “Trang chủ lenses”; “thg 10 2026 — stage 2 of 5” | “· Sân khấu” | 009_Trang_chủ_Hỏi_Nhân_sự.png |
| 11 | Trang chủ › Bảng vinh danh | 23 | 9 | “5 years with us”; “6 years with us”; “Birthday”; “Candour”; “Care” | “· Sân khấu” | 010_Trang_chủ_Bảng_vinh_danh.png |
| 12 | Trang chủ › Thông báo | 10 | 3 | “5 years with us”; “6 years with us”; “Announcements booked for the next seven days app”; “Birthday”; “Nothing is going out this week” | “· Sân khấu” | 011_Trang_chủ_Thông_báo.png |
| 13 | vận hành › Lương › Chạy lương | 2 | 1 | “Lương lenses”; “thg 10 2026 — stage 2 of 5” | “· Sân khấu” | 012_vận_hành_Lương_Chạy_lương.png |
| 14 | vận hành › Lương › Các đợt lương | 17 | 17 | “Construction”; “Construction Jun 2026 — Mid-Cycle Advance”; “Corporate Office”; “Demo Payroll June 2026 — Manufacturing”; “Demo Payroll June 2026 — Retail” | “· Sân khấu”; “Tháng chỉ tiến lên khi đợt lương chậm nh” | 013_vận_hành_Lương_Các_đợt_lương.png |
| 15 | vận hành › Lương › Các đợt lương › (detail) | 21 | 19 | “Construction”; “Construction Jun 2026 — Mid-Cycle Advance”; “Corporate Office”; “Demo Payroll June 2026 — Manufacturing”; “Demo Payroll June 2026 — Retail” | “· Sân khấu”; “Tháng chỉ tiến lên khi đợt lương chậm nh” | 014_vận_hành_Lương_Các_đợt_lương_detail_.png |
| 16 | vận hành › Lương › Phiếu lương | 2 | 1 | “Lương lenses”; “thg 10 2026 — stage 2 of 5” | “· Sân khấu” | 015_vận_hành_Lương_Phiếu_lương.png |
| 17 | vận hành › Lương › Phiếu lương › (detail) | 2 | 1 | “Lương lenses”; “thg 10 2026 — stage 2 of 5” | “· Sân khấu” | 016_vận_hành_Lương_Phiếu_lương_detail_.png |
| 18 | vận hành › Lương › Kết quả | 30 | 37 | “Approved”; “Construction”; “Construction”; “Construction Apr 2026 — Mid-Cycle Advance”; “Construction Jun 2026 — Mid-Cycle Advance” | “· Sân khấu” | 017_vận_hành_Lương_Kết_quả.png |
| 19 | vận hành › Lương › Đầu vào | 18 | 3 | “All”; “Create employee records from a file or a connect”; “Demo Payroll June 2026 — Corporate Office — awar”; “Demo Payroll June 2026 — Retail — awards”; “Done” | “· Sân khấu” | 018_vận_hành_Lương_Đầu_vào.png |
| 20 | vận hành › Lương › Chi trả | 10 | 17 | “Construction Apr 2026 — Mid-Cycle Advance”; “Construction May 2026 — Mid-Cycle Advance”; “Demo Payroll June 2026 — Corporate Office”; “Demo Payroll June 2026 — Retail”; “Logistics May 2026 — Mid-Cycle Advance” | “· Sân khấu” | 019_vận_hành_Lương_Chi_trả.png |
| 21 | vận hành › Lương › Điều chỉnh | 4 | 5 | “Basic Salary”; “Lương lenses”; “Payobook Retail — End-Month Payroll”; “thg 10 2026 — stage 2 of 5” | “· Sân khấu” | 020_vận_hành_Lương_Điều_chỉnh.png |
| 22 | vận hành › Lương › Quyết toán | 12 | 60 | “E-commerce · Sales Associate”; “E-commerce · Store Supervisor”; “Human Resources · Accountant”; “Human Resources · HR Officer”; “Infrastructure · QA Engineer” | “· Sân khấu” | 021_vận_hành_Lương_Quyết_toán.png |
| 23 | vận hành › Con người › Nhân viên | 34 | 64 | “Accountant”; “Area Manager”; “Cashier”; “Con người lenses”; “Dispatch” | — | 022_vận_hành_Con_người_Nhân_viên.png |
| 24 | vận hành › Con người › Nhân viên › (detail) | 38 | 64 | “Accountant”; “Area Manager”; “Cashier”; “Con người lenses”; “Dispatch” | — | 023_vận_hành_Con_người_Nhân_viên_detail_.png |
| 25 | vận hành › Con người › Hồ sơ | 37 | 53 | “Accountant”; “Area Manager”; “Birthday”; “Cashier”; “Column actions: Mã” | — | 024_vận_hành_Con_người_Hồ_sơ.png |
| 26 | vận hành › Con người › Lương | 38 | 24 | “Accountant”; “Area Manager”; “Cashier”; “Con người lenses”; “Construction” | — | 025_vận_hành_Con_người_Lương.png |
| 27 | vận hành › Con người › Nơi họ làm việc | 3 | 0 | “Con người lenses”; “October 2026”; “Payobook Vietnam JSC · VND” | — | 026_vận_hành_Con_người_Nơi_họ_làm_việc.png |
| 28 | vận hành › Con người › Tài sản | 10 | 0 | “Add an item”; “Add the first item”; “Con người lenses”; “Everything on this board, as a spreadsheet”; “New request” | — | 027_vận_hành_Con_người_Tài_sản.png |
| 29 | vận hành › Con người › Người mới | 41 | 20 | “% complete”; “% done”; “1 Oct”; “1 Sept”; “15 Sept” | — | 028_vận_hành_Con_người_Người_mới.png |
| 30 | vận hành › Con người › Thử việc | 26 | 21 | “1 Mar”; “14 days ago”; “2 things”; “3 course items outstanding”; “3 days ago” | — | 029_vận_hành_Con_người_Thử_việc.png |
| 31 | vận hành › Con người › Nghỉ việc | 41 | 19 | “% done”; “0% of the checklist done”; “1 Oct”; “12% of the checklist done”; “15 Sept” | — | 030_vận_hành_Con_người_Nghỉ_việc.png |
| 32 | vận hành › Con người › Hợp đồng | 26 | 18 | “1 Nov 2026”; “31 Jan 2027”; “Con người lenses”; “Contractor”; “December 2026” | — | 031_vận_hành_Con_người_Hợp_đồng.png |
| 33 | vận hành › Con người › Hợp đồng › (detail) | 30 | 19 | “1 Nov 2026”; “31 Jan 2027”; “Con người lenses”; “Contractor”; “December 2026” | — | 032_vận_hành_Con_người_Hợp_đồng_detail_.png |
| 34 | vận hành › Con người › Kế hoạch | 12 | 1 | “Board draft”; “Con người lenses”; “Each square is about 26 people”; “Keep this plan for everyone”; “Measure everything against this plan” | — | 033_vận_hành_Con_người_Kế_hoạch.png |
| 35 | vận hành › Tuyển dụng › Tổng quan | 38 | 32 | “25,484,253,037 ₫ of the Dispatch budget is unspe”; “48,050,245,113 ₫ of the E-commerce budget is uns”; “600,000,000 ₫ of the Quality Assurance budget is”; “600,000,000 ₫ of the Quality Assurance budget is”; “600,000,000 ₫ of the Quality Assurance budget is” | — | 034_vận_hành_Tuyển_dụng_Tổng_quan.png |
| 36 | vận hành › Tuyển dụng › Ứng viên | 11 | 29 | “Budi Santoso”; “Hiring Manager”; “John”; “Nhắc DEMO Hiring Manager”; “Nhắc DEMO Recruiter” | — | 035_vận_hành_Tuyển_dụng_Ứng_viên.png |
| 37 | vận hành › Tuyển dụng › Lời mời | 3 | 6 | “1 Oct”; “Tuyển dụng lenses”; “Where every offer is” | — | 036_vận_hành_Tuyển_dụng_Lời_mời.png |
| 38 | vận hành › Tuyển dụng › Phỏng vấn | 11 | 27 | “Arranged”; “Done”; “In person”; “John”; “Moved” | — | 037_vận_hành_Tuyển_dụng_Phỏng_vấn.png |
| 39 | vận hành › Tuyển dụng › Kho ứng viên | 14 | 13 | “1 Oct”; “15 Sept”; “Agronomy”; “Bahasa Indonesia”; “Budi Santoso” | — | 038_vận_hành_Tuyển_dụng_Kho_ứng_viên.png |
| 40 | vận hành › Lực lượng lao động › Hôm nay | 7 | 1 | “A JavaScript library for interactive maps”; “Leaflet”; “Zoom in”; “Zoom in”; “Zoom out” | “Không có ca, đấm hoặc rời đi vào ngày nà”; “Không có ca, đấm hoặc rời đi vào ngày nà” | 039_vận_hành_Lực_lượng_lao_động_Hôm_nay.png |
| 41 | vận hành › Lực lượng lao động › Lịch ca | 165 | 16 | “Accountant”; “Actual cost for this day”; “Area Manager”; “Cashier”; “Dispatcher” | “Tìm kiếm người, ống kính và hành động”; “Tìm kiếm người, ống kính, hành động…” | 040_vận_hành_Lực_lượng_lao_động_Lịch_ca.png |
| 42 | vận hành › Lực lượng lao động › Chấm công | 26 | 28 | “Accountant”; “Area Manager”; “Cashier”; “Consultant”; “Dispatcher” | “Tìm kiếm người, ống kính và hành động”; “Tìm kiếm người, ống kính, hành động…” | 041_vận_hành_Lực_lượng_lao_động_Chấm_công.png |
| 43 | vận hành › Lực lượng lao động › Nghỉ phép | 71 | 26 | “Asked for after the days had gone”; “Backdated”; “Facilities · 2026-10-01: 0”; “Facilities · 2026-10-02: 0”; “Facilities · 2026-10-03: 0” | “Tìm kiếm người, ống kính và hành động”; “Tìm kiếm người, ống kính, hành động…” | 042_vận_hành_Lực_lượng_lao_động_Nghỉ_phép.png |
| 44 | vận hành › Lực lượng lao động › Tăng ca | 21 | 3 | “All hours”; “Annual”; “Annual (special)”; “Bi-weekly”; “Daily” | “Tìm kiếm người, ống kính và hành động”; “Tìm kiếm người, ống kính, hành động…” | 043_vận_hành_Lực_lượng_lao_động_Tăng_ca.png |
| 45 | vận hành › Lực lượng lao động › Phê duyệt | 0 | 0 | — | “Hết tiền”; “Tìm kiếm người, ống kính và hành động” | 044_vận_hành_Lực_lượng_lao_động_Phê_duyệt.png |
| 46 | vận hành › Lực lượng lao động › Chốt kỳ | 9 | 1 | “Fri”; “Oct 19 · open”; “Oct 20 · open”; “Oct 21 · open”; “Oct 22 · open” | “Thiếu cú đấm”; “Tìm kiếm người, ống kính và hành động” | 045_vận_hành_Lực_lượng_lao_động_Chốt_kỳ.png |
| 47 | vận hành › Lực lượng lao động › Ngày lễ | 12 | 2 | “Collective leave”; “Company holiday”; “Compare entities”; “Every entry here changes how working days are co”; “Filter by entity” | “Tìm kiếm người, ống kính và hành động”; “Tìm kiếm người, ống kính, hành động…” | 046_vận_hành_Lực_lượng_lao_động_Ngày_lễ.png |
| 48 | vận hành › Lực lượng lao động › Hiện trường | 10 | 0 | “A JavaScript library for interactive maps”; “Demo mode”; “Field staff”; “Leaflet”; “Show route” | “Tìm kiếm người, ống kính và hành động”; “Tìm kiếm người, ống kính, hành động…” | 047_vận_hành_Lực_lượng_lao_động_Hiện_trường.png |
| 49 | vận hành › Chi phí › Công tác | 9 | 0 | “Authorized”; “Chi phí lenses”; “Draft”; “Finance”; “Hanoi” | “tiến lên” | 048_vận_hành_Chi_phí_Công_tác.png |
| 50 | vận hành › Chi phí › Công tác › (detail) | 0 | 0 | — | — |  |
| 51 | vận hành › Chi phí › Hoàn chi phí | 2 | 1 | “Chi phí lenses”; “Home” | — | 049_vận_hành_Chi_phí_Hoàn_chi_phí.png |
| 52 | vận hành › Chi phí › Hoàn chi phí › (detail) | 5 | 5 | “Back to "Chi phí"”; “Draft”; “Home”; “Meals · 10/16/2026”; “Waiting approval” | — | 050_vận_hành_Chi_phí_Hoàn_chi_phí_detail_.png |
| 53 | Hiểu › Phân tích › Tổng quan | 37 | 23 | “0 away on 2026-10-21”; “0 away on 2026-10-22”; “0 away on 2026-10-23”; “0 away on 2026-10-24”; “0 away on 2026-10-25” | — | 051_Hiểu_Phân_tích_Tổng_quan.png |
| 54 | Hiểu › Phân tích › Khám phá dữ liệu | 37 | 0 | “Across the group”; “Ask”; “Benefits & Allowances”; “Compare schemes”; “Component Explorer” | — | 052_Hiểu_Phân_tích_Khám_phá_dữ_liệu.png |
| 55 | Hiểu › Phân tích › Lực lượng lao động | 5 | 17 | “Nov 2026”; “Oct 2026”; “Open checkout”; “Phân tích lenses”; “Show the 1 affected employees” | — | 053_Hiểu_Phân_tích_Lực_lượng_lao_động.png |
| 56 | Hiểu › Phân tích › Lương | 2 | 2 | “Cashier”; “Phân tích lenses” | — | 054_Hiểu_Phân_tích_Lương.png |
| 57 | Hiểu › Phân tích › Ngân sách | 1 | 0 | “Phân tích lenses” | — | 055_Hiểu_Phân_tích_Ngân_sách.png |
| 58 | Hiểu › Phân tích › Tuyển dụng | 18 | 14 | “Afghanistan”; “Agency”; “Apr”; “Aug”; “Budi Santoso” | — | 056_Hiểu_Phân_tích_Tuyển_dụng.png |
| 59 | Hiểu › Phân tích › Đào tạo | 50 | 22 | “03 Aug: 0 set, 0 finished”; “05 Oct: 0 set, 0 finished”; “07 Sep: 0 set, 0 finished”; “10 Aug: 0 set, 0 finished”; “12 Oct” | — | 057_Hiểu_Phân_tích_Đào_tạo.png |
| 60 | Hiểu › Phân tích › Mục tiêu | 39 | 8 | “% along”; “1 agreed and locked”; “1 of 10 goal sheets agreed on DEMO Goal year 202”; “1 scored so far”; “Add a goal” | — | 058_Hiểu_Phân_tích_Mục_tiêu.png |
| 61 | Hiểu › Tuân thủ › Tờ khai | 9 | 0 | “Dossier Cover Sheet”; “Headcount Decrease”; “Headcount Increase”; “Labour Changes”; “Participant Schedule” | — | 059_Hiểu_Tuân_thủ_Tờ_khai.png |
| 62 | Hiểu › Tuân thủ › Ngân hàng | 3 | 0 | “Drop a bank confirmation letter / statement / pa”; “Tuân thủ lenses”; “Where every request is” | — | 060_Hiểu_Tuân_thủ_Ngân_hàng.png |
| 63 | Hiểu › Tuân thủ › Bảo vệ | 6 | 13 | “15 to under 18”; “Demo Minor 14 (Young Worker)”; “Demo Minor 17 (Young Worker)”; “Quality Assurance”; “Tuân thủ lenses” | — | 061_Hiểu_Tuân_thủ_Bảo_vệ.png |
| 64 | Hiểu › Tuân thủ › Nhật ký kiểm toán | 39 | 31 | “Approval”; “Approval”; “Approval workflow”; “Approval workflow”; “Approval workflow · 556” | “Diễn viên hàng đầu”; “Xuất khẩu” | 062_Hiểu_Tuân_thủ_Nhật_ký_kiểm_toán.png |
| 65 | Phát triển › Nhân tài › Mục tiêu | 28 | 11 | “2 days overdue”; “21 days overdue”; “32 days overdue”; “34 days overdue”; “35 days overdue” | — | 063_Phát_triển_Nhân_tài_Mục_tiêu.png |
| 66 | Phát triển › Nhân tài › Phát triển | 29 | 7 | “% of the time has gone”; “1 objective”; “All plans”; “Ask their manager”; “Being evaluated” | — | 064_Phát_triển_Nhân_tài_Phát_triển.png |
| 67 | Phát triển › Nhân tài › Đào tạo | 25 | 1 | “% done on average”; “2 courses · 60 people on them · 56 have not star”; “Assign a course”; “Assignments”; “Comes round again” | — | 065_Phát_triển_Nhân_tài_Đào_tạo.png |
| 68 | Phát triển › Nhân tài › Khen ngợi | 22 | 10 | “341 birthdays and work anniversaries in the next”; “All praise”; “Birthday and anniversary emails are switched off”; “Candour”; “Care” | — | 066_Phát_triển_Nhân_tài_Khen_ngợi.png |
| 69 | Phát triển › Học cùng Payobook › Bài học | 2 | 1 | “English”; “Học cùng Payobook lenses” | — | 067_Phát_triển_Học_cùng_Payobook_Bài_học.png |
| 70 | Phát triển › Học cùng Payobook › Nhóm | 6 | 30 | “Ash”; “Demo User”; “Học cùng Payobook lenses”; “Mitchell Admin”; “Nick” | — | 068_Phát_triển_Học_cùng_Payobook_Nhóm.png |
| 71 | Phát triển › Học cùng Payobook › Thiết lập | 1 | 1 | “Học cùng Payobook lenses” | — | 069_Phát_triển_Học_cùng_Payobook_Thiết_lập.png |
| 72 | Phát triển › Cài đặt › Công ty | 3 | 0 | “Settings groups”; “The details that print on payslips, filings and ”; “Your own name, address, tax numbers and logo.” | — | 070_Phát_triển_Cài_đặt_Công_ty.png |
| 73 | Phát triển › Cài đặt › Công ty › Công ty | 6 | 1 | “Back to "Cài đặt"”; “Danh sách View”; “Home”; “Kanban”; “Kanban View” | — | 071_Phát_triển_Cài_đặt_Công_ty_Công_tyCác_pháp_nhân_tiền_tệ_và_l.png |
| 74 | Phát triển › Cài đặt › Công ty › Người thuê nhà | 19 | 7 | “AB Mauri”; “Acme Manufacturing Co.”; “Alerts”; “Billing”; “Certificate expires 2026-11-12 (22 days left). M” | — | 072_Phát_triển_Cài_đặt_Công_ty_Người_thuê_nhàKiểm_soát_nhiệm_vụ_.png |
| 75 | Phát triển › Cài đặt › Công ty › Công ty của bạn | 43 | 4 | “A PNG or JPG under 4 MB. Drop one here, or choos”; “A letter”; “A statutory filing”; “Choose a picture”; “City” | — | 073_Phát_triển_Cài_đặt_Công_ty_Công_ty_của_bạnThe_details_that_p.png |
| 76 | Phát triển › Cài đặt › Công ty › Tập đoàn của bạn | 31 | 9 | “Construction”; “Construction”; “Corporate Office”; “Corporate Office”; “Group currency: VND” | — | 074_Phát_triển_Cài_đặt_Công_ty_Tập_đoàn_của_bạnCác_công_ty_trong.png |
| 77 | Phát triển › Cài đặt › Công ty › Tỷ giá | 2 | 1 | “Back to "Cài đặt"”; “Home” | — | 075_Phát_triển_Cài_đặt_Công_ty_Tỷ_giáMột_đồng_tiền_bằng_bao_nhiê.png |
| 78 | Phát triển › Cài đặt › Truy cập | 2 | 1 | “Settings groups”; “The agencies, trainers, insurers and software su” | — | 076_Phát_triển_Cài_đặt_Truy_cập.png |
| 79 | Phát triển › Cài đặt › Truy cập › Menu bên trái | 4 | 0 | “Manage roles”; “Off the left menu — press to put it back”; “On the left menu — press to take it off”; “This entry’s access is kept across module upgrad” | — | 077_Phát_triển_Cài_đặt_Truy_cập_Menu_bên_tráiMọi_mục_được_vẽ_đún.png |
| 80 | Phát triển › Cài đặt › Truy cập › Nhà cung cấp | 1 | 1 | “The vendor register could not be read” | — | 078_Phát_triển_Cài_đặt_Truy_cập_Nhà_cung_cấpWho_we_use_who_here_.png |
| 81 | Phát triển › Cài đặt › Truy cập › Quyền truy cập & bàn giao | 6 | 0 | “Alia Hoàng”; “Manage roles”; “People”; “Read and download the employee and contract data”; “Read the Records desk and the employee and contr” | — | 079_Phát_triển_Cài_đặt_Truy_cập_Quyền_truy_cập_bàn_giaoMọi_vai_t.png |
| 82 | Phát triển › Cài đặt › Lương | 1 | 0 | “Settings groups” | — | 080_Phát_triển_Cài_đặt_Lương.png |
| 83 | Phát triển › Cài đặt › Lương › Xưởng công thức | 52 | 18 | “Carry on setting up B6 Workbook walkthrough”; “Carry on setting up Indonesia Payroll”; “Carry on setting up Test”; “Carry on setting up Vietnam · Complete (guided s”; “Carry on setting up Vietnam · Monthly payroll — ” | — | 081_Phát_triển_Cài_đặt_Lương_Xưởng_công_thứcMọi_cấu_hình_cột_và_.png |
| 84 | Phát triển › Cài đặt › Lương › Cấu trúc lương | 5 | 1 | “Draft”; “India Standard Payroll”; “Indonesia Standard Payroll”; “Monthly”; “Vietnam Standard Payroll” | — | 082_Phát_triển_Cài_đặt_Lương_Cấu_trúc_lươngCấu_trúc_quy_tắc_và_n.png |
| 85 | Phát triển › Cài đặt › Lương › Bảo hiểm & Thuế | 5 | 2 | “Active”; “Health Insurance (BHYT)”; “Social Insurance (BHXH)”; “Test”; “Unemployment (BHTN)” | — | 083_Phát_triển_Cài_đặt_Lương_Bảo_hiểm_ThuếTỷ_lệ_đóng_góp_mức_trầ.png |
| 86 | Phát triển › Cài đặt › Lương › Cài đặt bảng lương | 2 | 0 | “Back to "Cài đặt"”; “Home” | — | 084_Phát_triển_Cài_đặt_Lương_Cài_đặt_bảng_lươngBiểu_mẫu_cấu_hình.png |
| 87 | Phát triển › Cài đặt › Nhân sự | 1 | 3 | “Settings groups” | — | 085_Phát_triển_Cài_đặt_Nhân_sự.png |
| 88 | Phát triển › Cài đặt › Nhân sự › Thiết lập tuyển dụng | 57 | 21 | “5 phiếu đánh giá · Recruiter review, Tech, Non-t”; “6 kênh · Careers page, LinkedIn, JobStreet (Indo”; “Afghanistan”; “Agency”; “Application not progressing” | — | 086_Phát_triển_Cài_đặt_Nhân_sự_Thiết_lập_tuyển_dụngCác_giai_đoạn.png |
| 89 | Phát triển › Cài đặt › Nhân sự › Mẫu đơn ứng tuyển | 17 | 27 | “Are you willing to relocate for this role?”; “Bahasa Indonesia”; “Country you live in”; “Do you have the right to work in this country?”; “Email address” | — | 087_Phát_triển_Cài_đặt_Nhân_sự_Mẫu_đơn_ứng_tuyểnCác_câu_hỏi_ứng_.png |
| 90 | Phát triển › Cài đặt › Nhân sự › Quy tắc tuyển dụng | 10 | 2 | “Back to "Cài đặt"”; “Company”; “Country”; “DEMO Recruiter”; “Hiring rules” | — | 088_Phát_triển_Cài_đặt_Nhân_sự_Quy_tắc_tuyển_dụngMỗi_công_ty_và_.png |
| 91 | Phát triển › Cài đặt › Nhân sự › Hội đồng chấm theo tiêu chí nào | 17 | 10 | “Back to "Cài đặt"”; “Can they do the job”; “Company”; “Five: a person outside their field would have fo”; “Five: given a problem they had never seen, they ” | — | 089_Phát_triển_Cài_đặt_Nhân_sự_Hội_đồng_chấm_theo_tiêu_chí_nàoNă.png |
| 92 | Phát triển › Cài đặt › Nhân sự › Kiểm tra lý lịch gồm những gì | 19 | 12 | “A government photo ID, and the name on it matche”; “Back to "Cài đặt"”; “Both spoken to, and at least one of them managed”; “Company”; “Criminal record check” | — | 090_Phát_triển_Cài_đặt_Nhân_sự_Kiểm_tra_lý_lịch_gồm_những_gìMỗi_.png |
| 93 | Phát triển › Cài đặt › Nhân sự › Người sắp vào làm được yêu cầu những gì | 19 | 12 | “A clear photograph or scan of the page with your”; “A photograph of you”; “A photograph of your bank card or the top of a s”; “Back to "Cài đặt"”; “Company” | — | 091_Phát_triển_Cài_đặt_Nhân_sự_Người_sắp_vào_làm_được_yêu_cầu_nh.png |
| 94 | Phát triển › Cài đặt › Nhân sự › Hành trình | 26 | 34 | “% done”; “1 Oct”; “1 Sept”; “11 Oct”; “15 Sept” | — | 092_Phát_triển_Cài_đặt_Nhân_sự_Hành_trìnhCác_bước_của_từng_người.png |
| 95 | Phát triển › Cài đặt › Nhân sự › Các mẫu | 8 | 0 | “An announcement somebody has already written onc”; “Announcement templates”; “Back to "Cài đặt"”; “Company”; “Home” | — | 093_Phát_triển_Cài_đặt_Nhân_sự_Các_mẫuThe_town_hall_the_holiday_.png |
| 96 | Phát triển › Cài đặt › Nhân sự › Người phụ trách | 7 | 0 | “Back to "Cài đặt"”; “Company”; “Home”; “New announcements arrive with the company's HR l”; “The HR lead, unless you say otherwise” | — | 094_Phát_triển_Cài_đặt_Nhân_sự_Người_phụ_tráchThe_HR_lead_of_eac.png |
| 97 | Phát triển › Cài đặt › Phê duyệt | 1 | 0 | “Settings groups” | — | 095_Phát_triển_Cài_đặt_Phê_duyệt.png |
| 98 | Phát triển › Cài đặt › Phê duyệt › Ma trận phê duyệt | 27 | 4 | “Announcement”; “Approver · whole company”; “Bank account change”; “Contract extension”; “Decided with another” | “Hết tiền” | 096_Phát_triển_Cài_đặt_Phê_duyệt_Ma_trận_phê_duyệtMọi_quy_trình_.png |
| 99 | Phát triển › Cài đặt › Phê duyệt › Hộp thư phê duyệt | 0 | 0 | — | “Hết tiền” | 097_Phát_triển_Cài_đặt_Phê_duyệt_Hộp_thư_phê_duyệtMọi_thứ_đang_c.png |
| 100 | Phát triển › Cài đặt › Kết nối | 1 | 0 | “Settings groups” | — | 098_Phát_triển_Cài_đặt_Kết_nối.png |
| 101 | Phát triển › Cài đặt › Kết nối › Tích hợp | 11 | 7 | “Connected”; “DarwinHR (Darwinbox)”; “Demo / Stub”; “Deputy”; “Disconnected” | — | 099_Phát_triển_Cài_đặt_Kết_nối_Tích_hợpNgôi_nhà_duy_nhất_cho_các.png |
| 102 | Phát triển › Cài đặt › Kết nối › Ánh xạ | 14 | 1 | “A historical run record; it may be for a differe”; “Application sources”; “Find a component”; “INCENTV”; “Input components” | — | 100_Phát_triển_Cài_đặt_Kết_nối_Ánh_xạKết_nối_bất_kỳ_nguồn_nào_ng.png |
| 103 | Phát triển › Cài đặt › Hệ thống | 7 | 3 | “Every update we have shipped, newest first, in p”; “Plan & usage”; “Plan & usage”; “Settings groups”; “What's new” | — | 101_Phát_triển_Cài_đặt_Hệ_thống.png |
| 104 | Phát triển › Cài đặt › Hệ thống › Cấu hình mới | 5 | 2 | “Pick every group that applies. It decides which ”; “Setup steps”; “The months that are not ordinary. Tick them now ”; “Vietnam Standard 2026”; “Vietnam · Complete” | “Xem lại sổ làm việc tính lương, giữ lại ” | 102_Phát_triển_Cài_đặt_Hệ_thống_Cấu_hình_mớiSáu_bước_từ_điểm_bắt.png |
| 105 | Phát triển › Cài đặt › Hệ thống › What's new | 4 | 7 | “3 September 2026”; “What's new”; “You are on release”; “You are on this release” | — | 103_Phát_triển_Cài_đặt_Hệ_thống_What_s_newEvery_update_we_have_s.png |
| 106 | Phát triển › Cài đặt › Hệ thống › Plan & usage | 8 | 1 | “Employees on Payobook”; “Every invoice we have sent you, newest first. Th”; “No invoices yet.”; “October 2026”; “Payobook raises one invoice a month, after the m” | — | 104_Phát_triển_Cài_đặt_Hệ_thống_Plan_usageYour_plan_how_many_emp.png |
| 107 | Phát triển › Cài đặt › Hệ thống › PayAI được làm | 2 | 0 | “Back to "Cài đặt"”; “Home” | — | 105_Phát_triển_Cài_đặt_Hệ_thống_PayAI_được_làmBật_những_việc_Pay.png |
| 108 | Phát triển › Cài đặt › Hệ thống › Dữ liệu mẫu | 12 | 8 | “Back to "Cài đặt"”; “Company”; “DEMO HR programme data”; “DEMO Lifecycle journeys”; “Demo data” | — | 106_Phát_triển_Cài_đặt_Hệ_thống_Dữ_liệu_mẫuFive_demo_people_with.png |

## D. Glossary draft (`VIFIX_GLOSSARY.md`, built by `tools/vifix_glossary_build.py`)
**205 terms** (Pay 59, App 44, People 30, Statutory 25, Time 15, Approvals 15, Hiring 12, Expenses 5), each with the
ONE Vietnamese to use, every current variant with counts, Learn's term, and a reason. **25 are marked REVIEW** for the
owner (listed in the open questions where they change what people see). It starts from Learn's 113 authored terms and the
Vietnamese payroll vocabulary (BHXH/BHYT/BHTN, thuế TNCN, người phụ thuộc, giảm trừ gia cảnh, ngày công, mức trần đóng
bảo hiểm, phần người lao động / phần doanh nghiệp). Where Learn and the screens disagree it is marked REVIEW, not decided.

## E. Replica drift (`tools/vifix_replica_drift.py`)
All **55 practice copies** (every builder in `screens.js`) plus the rail/tabs row, against their real templates, the
components and Python behind them, and the live `vi_VN.po`. **47 of 56 rows drift: 62 English labels and 171 Vietnamese
labels** (+21 Vietnamese marked "(?)", not counted); real screen not found: 0. Known items: Today ("Checked out" copy
"Đăng xuất", screen "đã về"), Close (week heading, three flag names, "Flags this week"), Overtime "Near the limit" chip
(gone), Records wide layout ("Export with data"/"Import a file" only inside the File menu now), Govt filings line (real:
"Statutory filings for {company} · {country}"): found. "Headcount Increase" is **not** drift (both sides print the same
Python pair). Note: in about a quarter of the Vietnamese drift the practice copy is the better Vietnamese; the fix
belongs in the product `.po`, not the copy. Full table: `p1_out/replica_drift.md`.

| Replica | Real template(s) | Drift EN+VI | Drifted English (sample) | Vietnamese drift (sample) |
|---|---|---|---|---|
| runpayroll | payrun_wizard.xml | 2+12 | "Add pay data"; "Pay run for" | scheme groups translated on the copy, English on screen; "đã tính toán" |
| statutory | statutory.xml | 5+9 | "Policy history"; "Tax brackets (progressive)"; "per dependant" | "sơ đồ" for Scheme; "bảng thuế" |
| mapping_sheet | mapping_studio.xml | 2+11 | "Columns wired to the scheme" | Pay run → "kỳ lương"; Pay month/year English on screen |
| formula | studio.xml, studio_experience.xml | 2+10 | "How a configuration goes live" | "máy tính ưu đãi"; "chuyện gì xảy ra nếu" |
| insights | insights.xml | 5+6 | "Employee leg"; "Employer leg"; "Joiners this month" | run states English on screen |
| payruns | payruns.xml | 4+7 | "How a run travels"; "Showing all" | "hồ sơ ngân hàng"; "kỳ lương" |
| import | import.xml | 1+8 | "rows" | 5 tile labels English on screen; "lô gần đây" |
| importwizard | import_wizard.xml | 3+6 | "File upload"; "Overtime amount" | "thời gian và hồ sơ" |
| treatment | component_treatment.xml | 1+8 | long hours warning | as mapping |
| mapping | journey_board.xml, mapping_studio.xml | 0+8 | — | "khoản lương theo hợp đồng"; Transformations English |
| explorer | explorer.xml | 1+6 | "Run state" | "khối"; "phương án lương" |
| hiringrole | hiring_board_p1/p4/p5/p6.xml | 0+7 | — | Drop-out / Interview reject English on screen |
| matrix_builder | builder.xml | 0+7 | — | "phê duyệt chung" |
| approvals | inbox.xml | 1+5 | "waiting — your turn" | "tổng thu nhập" |
| integrations | integrations.xml, connector_cockpit.xml | 2+4 | "Arrivals from the connected system" | "mở bản đồ"; "hồ sơ dàn dựng" |
| wfclose | pb_close_lens.xml | 5+1 | "Flags this week"; "Missing check-out" | — |
| wftoday | pb_today.xml, pb_dock.xml | 4+2 | "Leave requests"; "Overtime to approve" | "Đăng xuất" vs "đã về" |
| employees | people.xml, contract_360.xml | 1+4 | "No running contract" | "Payroll ready" English on copy |
| govreports | govt_reports.xml | 1+4 | "Statutory filings for this company…" | "Kết xuất" vs "tạo" |
| records | records_desk.xml | 4+0 | "Export with data"; "Import a file" | — |
| (27 more rows) | | | see `p1_out/replica_drift.md` | |

## F. Wave plan (`tools/vifix_wave_plan.py --split 2`)
Ordered by how many people see the screen. Counts are installed modules only. "Rewrite" = existing Vietnamese to correct
(.po only). "New" = strings that need a first translation (regenerate the module's `.pot`, merge, translate). "Code" =
wrap in `_t()`/`_()` or rebuild a glued sentence before translating. "Stored" = rewrites that are field labels, menus or
choices, stored per database, so the deploy needs the guarded overwrite load (LR20/LR29) on 4 databases; everything else
loads with a restart. Days are estimates (rewrite 250/day, new 200/day, code 120/day, markers 400/day, +0.5 day for a
guarded load).

| Wave | Area | Who sees it | Modules | Rewrite | New | Code | Never load | Stored | Sub-waves | Days | Risk |
|---|---|---|---|---|---|---|---|---|---|---|---|
| W1 | Home, the app frame and the employee's own pages | everyone who signs in: staff on Home, every employee on My Payobook | 14 | 23 | 404 | 91 | 1 | 7 | 3 | 4.3 | normal |
| W2 | Approvals (the inbox and every approval card) | every approver and requester | 4 | 4 | 252 | 8 | 74 | 1 | 2 | 2.0 | normal |
| W3 | Payroll: running a month | payroll staff every month | 14 | 61 | 502 | 274 | 26 | 37 | 6 | 7.6 | normal |
| W4 | Payroll: setup, formulas and the Vietnamese rules | payroll leads and implementers | 9 | 638 | 536 | 622 | 44 | 497 | 6 | 13.6 | higher: many stored labels |
| W5 | People and the joining-to-leaving boards | HR every day | 12 | 10 | 1075 | 123 | 37 | 6 | 7 | 8.1 | normal |
| W6 | Hiring and Talent | HR and hiring managers | 5 | 29 | 1223 | 151 | 0 | 0 | 4 | 7.5 | low |
| W7 | Time, leave and expenses | HR, team leads and every employee who clocks in or claims | 15 | 132 | 344 | 71 | 24 | 72 | 5 | 5.5 | higher: many stored labels |
| W8 | Insights and Compliance | managers, finance and compliance | 17 | 242 | 274 | 205 | 22 | 203 | 6 | 7.1 | higher: many stored labels |
| W9 | Settings, access, connections, PayAI and the rest | administrators; the tenant console only the Payobook team | 16 | 86 | 1375 | 404 | 88 | 65 | 7 | 13.9 | higher: many stored labels |
| **All** | | | 106 | 1225 | 5985 | 1949 | 316 | 888 | 46 | **69.6** | |

Each wave is cut into 1–2 day sub-waves by module (46 in all; `p1_out/wave_plan.md`). Five single modules are bigger than
two days and should be split by screen inside the module: pb_payroll_templates (W3), pb_hr_payroll_formula and
pb_formula_studio (W4), pb_goals (W6), pb_tenants (W9, the tenant console only the Payobook team sees: the obvious one
to defer). Suggested order inside every wave: glossary terms first, then code wrapping, then `.pot` regeneration and
translation, then the rewrites; gate on the scans (pot_dropped, markers, suspicious, word_order and the
`*_wrapped_uncovered` classes at 0 for the wave's modules) and a sweep of the wave's screens on a clone.
Not in any wave: the 10 modules not installed on payobook (the six legacy country payroll modules, pb_hr_workforce_planning,
pb_payroll_mapping_vn, biztinct_website, and biz_host_db, which is loaded server-wide and has no screen text), and Learn
(LEARNREV).

## New ledger rows
VF2 `.pot` merge drops `.po`-only entries · VF3 Python looks only in its own module, JS everywhere · VF4 3,197 Python
strings never added · VF5 442 never-loading entries · VF6 stray % only matters in Python · VF7 Title Case word order =
machine output · VF8 clone: language on the partner, jobs off in the restore script, own odoo-bin · VF9 QA user's missing
tabs, hubs reopen on the last tab, section toggles · VF10 the seed list. Details in `VIFIX_LEDGER.md`.

## Open questions for the owner
1. **What do we call a pay run?** Screens say "đợt lương"; Learn's card says "đợt tính lương"; 10 places say "kỳ lương",
   which really means the pay period. Recommend "đợt lương" everywhere (short, already on the main screens). Learn's
   card would change to match.
2. **The "People" menu.** It says "Con người" (human beings, a philosophy word). Vietnamese HR software says "Nhân sự".
   Changing it renames a menu every staff user sees, and Learn's breadcrumbs ("Con người › …") would follow.
3. **The "Workforce" menu.** "Lực lượng lao động" means the national labour force. The area holds shifts, attendance,
   time off and overtime. Options: "Công và ca", "Chấm công", or keep it. Same question for the rail section names
   "vận hành / Hiểu / Phát triển" ("Hiểu" = "understand").
4. **Division.** Most of our files say "Khối"; Learn says "Bộ phận", which Vietnamese also uses for a department. Recommend
   "Khối" so division and department never share a word.
5. **Overtime.** Screens say "Tăng ca"; the Labour Code says "làm thêm giờ". Recommend "Tăng ca" on everyday screens and
   "làm thêm giờ" only on statutory reports. Or one word everywhere?
6. **English loanwords.** "email", "file", "demo", "online" appear in 375 Vietnamese strings. Keep the ones Vietnamese
   offices say every day ("email") and use Vietnamese for the rest ("tệp" for file)? Or keep them all?
7. **Dates on Vietnamese screens** show English months ("Thu 17 Sept", "Oct 2026") and the short "thg 10 2026". Recommend
   "Thứ Năm, 17/9" and "Tháng 10/2026". This is code in several screens, not just translation.
8. **Pay-run names** are created in English ("… — End-Month Payroll · October 2026") and stay in the records. Should new
   runs be named in the company's language, and should existing demo runs be renamed?
9. **The tenant console (Settings for the Payobook team, 911 strings, about 5 days)**: translate now, later, or never
   (only the Payobook team sees it)?
10. **Practice copies** where the copy's Vietnamese is better than the real screen's: fix the product to match the copy
    (recommended), so lessons and screens agree.

## Commits (`git log f4b3b9492..vifix-p1`)
- e86cde94a tools(vifix): P1 scope E replica drift over all 55 practice copies; sweep fixes
- 928134503 docs(vifix): P1 scope D glossary draft (205 terms, 25 for review) and wave planner
- 18b11de7f tools(vifix): po scan — word-order check and 15 more literal-translation seeds
- 0f4c2412f tools(vifix): P1 scopes B and C — literal scan, live sweep and its classifier
- 190c371f5 tools(vifix): P1 scope A — static vi_VN.po scan reproducing the server's .pot merge
- (this report, ledger rows VF2–VF10 and p1_out baseline: the last commit)
