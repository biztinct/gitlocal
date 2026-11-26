# DOCSTUDIO close-out — Stream D (merge, deploy, owed checks) — REPORT

Merge-deploy agent, 2026-11-26 (UTC). Handover `DOCSTUDIO_CLOSE_HANDOVER.md` §Stream D, ritual of
`DOCSTUDIO_W2_DEPLOY_HANDOVER.md` / W1A. Scripts `docs/handovers/docstudio/cd/` (clones of `w2/` and
`pdffix/`). Paused once (coordinator, owner offline, ~03:00 UTC) after the go-live and its verification;
resumed ~08:00 UTC and finished the owed checks (§6b).

**Result: merged and pushed to `19.1` at `06defa5ae`; LIVE on all five databases** (payobook,
payobook_template, p0clone, rize, sudima) on 26 Nov, service stopped 02:45:11, up 02:53:19 UTC —
**488 s down**. abm untouched. Nothing failed, nothing restored.

## 1. Merge

Worktree `gitlocal-worktrees/docstudio-cd`, branch `docstudio-cd-merge` from `origin/19.1` @ `3d038fcc9`.

| Commit | What |
|---|---|
| `d8876ea1e` | merge `origin/docstudio-close-l` @ `870998406` (`--no-ff`), no conflict |
| `fc2c1153a` | merge `origin/docstudio-close-z` @ `959c3f92a`; conflicts in 3 manifests only (version lines), resolved to the higher version, both changes kept: pb_doc_studio 19.0.1.5.0, pb_doc_studio_hiring 19.0.1.2.0, pb_doc_contracts 19.0.1.2.0 (above L's 1.4.1 / 1.1.1 / 1.1.1) |
| `876facb5b`, `80aaded45` | deploy scripts `cd/` |
| `06defa5ae` | merge of `origin/19.1` (`8eb27c95e`, NEWHIRE P8 docs only) — pushed `8eb27c95e..06defa5ae`, fast-forward, no force |

- No module of this release was touched on `19.1` since either branch point. Module trees = the
  builders' tips except the three shared modules (= both tips combined).
- Static gates: Python compiles, XML parses, PO files parse (0 empty, 0 duplicate, 0 vendor word);
  no vendor word in any added user-visible string; `pb_learn/i18n/vi_VN.po` unchanged by the merge
  (171 msgid, = live before and after). Unpushed diff scanned: no passwords/keys; no `outputs/`,
  `SUDIMA/`, `RIZE/`.

## 2. Local tests (one database `docstudio_cd_t` = copy of `nh12_base`; dropped with its file folder)

| Run | Result |
|---|---|
| install/upgrade of the 12 modules | exit 0 |
| pb_learn + pb_payroll_ai_insights + 8 studio suites (708 tests) | 7 failed + 1 error = **exactly L's baseline**: pb_learn's known 5 (registry 05, composer 03b, guide truth 02/02b, learnrev P4 c1), ai_insights test_egress 04e, pb_doc_contracts test_01 (install-order artefact of the local copy), pb_doc_studio_me a1_12 (no PDF engine on this Mac) |
| pb_hiring (532 tests on this copy) | 9 failed + 2 errors = the recorded 10 **+ TestRegistersP9.test_06** ("joined this month" tile). Re-run on the **unchanged origin/19.1 code** on a fresh copy of the same base: test_06 fails there too (and test_08) → pre-existing on this base copy, not this release |
| pb_hr_payroll_analytics | 3 tests, 0 failed |

No wkhtmltopdf on the Mac (nothing installed); real PDFs were checked on the server.

## 3. Rehearsal (hidden copies of payobook AND rize, jobs + mail servers off first, both dropped)

Both: `-u` of the 12 modules exit 0, 0 ERROR, 0 Traceback (payobook 97 s, rize 76 s); every module
at the shipped version; counts identical except rize messages +4 (technical change notes, as earlier
releases); phase F golden: 9 letters **identical**, template rows identical except the **name** of
rows 10 and 11 (the two built-in offer letters gain vi/id names — Z3, by design); A1 golden: English
offer letters and certificates **identical**, only "template rows" (same names) differ. Probe with real
PDFs after: see §5 (same results).

## 4. Go-live

Prep 02:20–02:24 (dumps ×5 + file folders linked, live trees = origin/19.1 trees, counts, job
snapshots, probe). NEWHIRE P8 had closed its START (DONE 02:13) and released the lock before ours.
START 02:42; quiet 15 min on rize/payobook/sudima; backups ×5 again; notes re-read; stop 02:45:11.
Per-module scoped rsync of the 12 trees (staged = commit), then `-u` one database at a time:

| Database | exit / time | jobs active before → after | backup right before the stop |
|---|---|---|---|
| payobook_template | 0 / 76 s | 40 → 40 | golive-payobook_template.dump 32.1 MB |
| p0clone | 0 / 74 s | 49 → 49 | golive-p0clone.dump 32.7 MB |
| sudima | 0 / 75 s | 91 → 91 | golive-sudima.dump 36.3 MB |
| rize | 0 / 79 s | 92 → 92 | golive-rize.dump 46.7 MB |
| payobook | 0 / 92 s | 59 → 59 | golive-payobook.dump 82.8 MB |

No job re-activated, no new job row. Asset purge + `web.assets.version` = `docstudio-close-20261126T0222Z`
+ signalling row per database. Five sites warmed 200. DONE 02:53, verification NOTE 03:03, lock
removed. Backups `/odoo/backups/docstudio-close-20261126T0222Z/` (prep + go-live dumps, file folders,
`previous-trees.tgz`).

## 5. Verification (`/tmp/cd-20261126T0222Z/verify.txt` on the server)

- 12 trees byte-identical to `06defa5ae`; manifest = installed version, 12/12 ×5.
- Data right before the stop vs after: identical ×4, rize messages +4. Expected moves only:
  offer-letter names (vi/id added), three analytics reports' Print-menu link → none. Letter wording,
  letters, vault documents, offers, certificates, saved reports, mail queue, Learn progress identical
  prep → before → now ×5 (nothing mailed).
- Probe (administrator, real PDFs, rolled back):
  - **Z1** payobook, untouched built-in offer letter with monthly + one-off lines: no choice → English
    words (as before); Indonesian → "Setiap bulan" / "Sekali saja" in the letter AND in the real PDF;
    Vietnamese → "Hằng tháng" / "Một lần" in the letter AND the real PDF. Other databases have no
    offer with pay lines.
  - **Z2** the three analytics PDFs on no Print menu ×5.
  - **Z3** both offer letters + Vietnam contract: names in vi/id, name box = gallery card ×5.
  - **Z4** Vietnam contract, person with no own language: designer picks Vietnamese = contract panel
    (before: English) on payobook and rize; sample PDF Vietnamese, no "No wording" line, no sample note.
    p0clone has no such person.
  - **L** lessons L43–L48 in the shipped file ×5, 0 vendor word.
- Compiled screen code ×5: Z4 flag, the new anchors, Learn practice copies, spotlight re-place.
- Server log since the stop: 0 ERROR, 0 Traceback, 0 asset errors; rehearsal copies 0.

## 6. Browser walk on payobook.com (Chrome MCP, isolated context, QA login), first pass

Done (nothing saved; QA language put back to English; signed out; page closed):
- Settings › HR › Documents on **Vietnamese** screens: cards "Thư mời làm việc", "Thư mời làm việc —
  Việt Nam", "Hợp đồng lao động — Việt Nam"; name box of the Vietnam offer letter in Vietnamese. On
  **Indonesian** screens: "Surat penawaran", "Surat penawaran — Vietnam", name box the same.
- Offer letter preview with a real offer (Ngo Thanh Tam): pay table "Setiap bulan" (Indonesian),
  "Hằng tháng" (Vietnamese).
- Vietnam contract designer (Vietnamese screens), person Bùi Anh Cường: preview language opens on
  **Vietnamese / Tiếng Việt** by itself, no "No wording" line, sample note on screen; "Tải PDF mẫu" →
  real PDF (caught from the page's own request): Vietnamese wording, no note, 1 page.
- Hiring › DEMO Farm Supervisor › Details › Offer & joining › Offer: **"Language: English (US),
  automatic (the company's language)"** box beside "Read the letter" with English / Indonesian /
  Vietnamese — seen, not changed.
- Six new lessons (L43–L48) in **English**: each opens; 40 / 40 steps, the highlight sits on its
  control (within a few pixels).
- Hidden analytics PDFs: the QA login cannot open those pages at all (payroll managers only), so the
  Print menu could not be looked at in a browser; proven server-side (§5).

## 6b. Owed checks after the resume (payobook.com, Chrome MCP isolated contexts)

| # | Check | Result |
|---|---|---|
| 1 | Six lessons in **Vietnamese**, QA login | **40 / 40 steps, highlight on its control** (L43 6, L44 7, L45 8, L46 6, L47 6, L48 7); titles and lines in Vietnamese. QA language back to English. Console: **0 errors, 0 warnings**. |
| 2 | Console, one pass each: Documents gallery + designer (Page tab), contract panel › Contract document, Build a report → saved → PDF designer → Download PDF ("3 rows, made in 3.5 seconds"), Explorer saved view → PDF → Download ("6 rows, 2.6 s"), Hiring offer panel (language box) | **0 errors, 0 warnings** on every screen. Fonts offered: Clean, Classic serif. Contract sheet: Download PDF, Save to documents · v1, sample-wording line. The walk's report and view (`DEMO CD walk …`) deleted again with the QA login; 0 PDF looks stored. |
| 3 | HR-officer login | **Not done as a signed-in HR officer.** No existing demo login is a clean HR officer (the demo visitor also sees Payslips and Formula Engine; others are outside sign-ups). One login `DEMO CD HR Officer` was made with the Access screen's own method, but **giving it a role through the Access screen goes to the owner for approval** ("Sent for approval — Mitchell Admin"); I did not bypass it. Both test requests were withdrawn; the login (no role) is **archived**; its two invitation mails were stopped by the system ("test or demo address"). There is also no plain "HR officer" role in the Access catalogue (nearest: "Time off officer", which implies it). **Server check instead** (live code, synthetic person with the Time off officer groups, rolled back): Insights on the side menu = on; Build a report opens; Pulse / Explorer / payroll insights refused; 8 examples, 4,554 rows, save works, Excel file made; Contracts and Applicants locked with "You cannot see contracts. Ask your administrator for contract access."; a contract pay field asked for by name is refused with the same sentence. |
| 4 | View-only on a contract | **Cannot exist today** (evidence, live code): opening the contract panel needs HR officer, payroll officer or administrator (`pb.contracts._cd_require_read`: "You do not have access to contracts. Ask an administrator for the HR or Payroll Officer role."); "Save to documents" and its server method `contract_document_save` check `pb.employee.document` create (`_pbdc_may_file`), which HR officer, payroll officer/manager, HR manager, system **and every internal login** hold (the My Payobook self-upload row "ess employee document self-upload", `pb_me_portal`, limited by a record rule to one's own record). Access roles checked (`cd/cd_roles_find.py`): every role that reads contracts also passes that check. **Guard still works** (`cd/cd_viewonly_guard.py`, rolled back): an HR officer and a no-role user behave as A2 test 11 (no-role refused, button hidden); a pay-seeing reader with document create taken away (inside the transaction) gets no Save button, the sentence "You can download this contract. Filing it in the employee's documents needs the HR or payroll role.", **download works**, and the **server refuses** filing; the sample note is on screen and not in the PDF (test 16). No login was created for this. What would have to change: a "contracts — can look" role that opens the panel without the HR/payroll officer role, and `_pbdc_may_file` reading a real filing permission (not plain document create). |
| 5 | Phone width (400 px) | Documents gallery: no sideways scroll, readable; the side rail stays open (about 120 px) and the first card is almost two screens down. Lesson (L45): works, card docks at the bottom, highlight on the control; the PayAI button covers the corner of the lesson's bottom bar. **PDF designer: cramped header** — the title is covered by the "Standard look" chip, "Save look" / "Download PDF" wrap to two lines, settings take the top half over a small preview. Not fixed. |

Everything made for the checks is gone or archived: walk report and view deleted, DEMO CD HR Officer
archived (no role), approval requests withdrawn, no synthetic login left (`demo.cd.%` active: 0), QA
language English, all browser contexts signed out and closed. The PDF captured from the designer was
moved out of the repo (ledger DS-CD-4).

## 8. Ledger rows

- DS-CD-1 | `ROLLBACK TO SAVEPOINT` in a shell probe leaves the ORM cache holding records that no
  longer exist (next step: MissingError) | `env.flush_all()` before, `env.invalidate_all(flush=False)` after.
- DS-CD-2 | PDF text of Vietnamese words may not match a plain `in` (decomposed accents / spacing) |
  compare NFC with spaces removed.
- DS-CD-3 | `res.company.country_id` is not stored: a domain on `company_id.country_id` fails | use
  `company_id.partner_id.country_id`.
- DS-CD-4 | Chrome MCP `get_network_request` with a relative file path writes into the MAIN checkout's
  root | move the file out at once (done) — never leave it in the repo.
- DS-CD-5 | Giving a role through the Access screen can need the owner's approval; a check that needs a
  role cannot be finished alone | withdraw the test request (`biz.approval.engine.cancel`), archive the
  login, check server-side with a synthetic user, say so.
- DS-CD-6 | "May file" on the contract panel = document create, which every internal login holds via the
  My Payobook self-upload permission | a true view-only reader needs a different check (owner decision).
