# JOINING — ledger (rules, decisions, gotchas)

Every JOINING handover and report references this file. Append new entries; never renumber.

## 1. Standing rules (owner; apply to all work in this repo)

- R1. **White-label:** the word "Odoo" never appears in anything a user can see or receive — labels, tooltips,
  help, placeholders, empty states, toasts, errors, menu names, field `string=`/`help=`, selection labels,
  reports, emails, public pages, manifest `name`/`summary`, `.po` msgstr. Say "Payobook" or a neutral word.
  Technical identifiers (`from odoo import`, module/model/xml ids, comments, docs) are never rewritten.
- R2. **One addons directory** on the server: `/odoo/odoo-server/addons`. Never create a second. Never
  `rsync --delete` into the addons root. Never deploy this repo's copies of standard addons.
- R3. **Five databases:** payobook, payobook_template, p0clone, rize, sudima. **Never `abm`.**
- R4. **Release only through `tools/release.sh`**, after reading `/opt/deploy-notes.md`.
- R5. **Browser validation is mandatory.** No screen is "done" from tests alone; use it in a browser with the
  console open.
- R6. **Design mandate:** "extreme WOW, best in class", Lucide icons only, never emoji, no gradients, one solid
  primary button per bar, the indigo system (`#5A4BB0`).
- R7. **Whatever is possible from the back end must have a screen twin.** No ability that exists only as a
  server method or a parameter.
- R8. **No parallel engines.** One catalogue of what is asked (Add employee step 5), one bank format
  (`pb.bank.format`), one create path for an employee (the studio's `send`).
- R9. **Demo data:** never delete demo data on payobook; demo records are prefixed `DEMO`; never the word
  "RIZE" in demo records. rize and sudima are client databases — create nothing there.
- R10. **No credentials in the repo**, ever. No real personal data in tests or fixtures.
- R11. **Translations from day one:** `_t` / `_()` on every string; `.pot` + `vi_VN.po` + `id_ID.po`; three
  markers per PO entry; append PO entries as text.
- R12. **One feature = one commit, pushed to 19.1.** Explicit file staging.
- R13. **Tenant email is off on purpose** on rize, sudima, p0clone. Every email step needs a no-email twin.
- R14. **Words for the owner are plain English** (screen words, no code names). Technical language belongs in
  commits, comments, handovers and reports — but the report's "open questions for the owner" section is plain.

## 2. Decisions specific to JOINING

- J-D1 (2026-11-27, owner). One-time code, no password. Reverses NEWHIRE D8 for this portal only; every other
  token page keeps its doctrine.
- J-D2 (owner). Code by email where possible; HR "Copy link" + "Show a code" everywhere. No SMS/WhatsApp.
- J-D3 (owner). Joining board in Hiring and in People.
- J-D4 (owner). Finger-drawn signature.
- J-D5 (owner). "Invite someone" for people hired outside Hiring.
- J-D6 (owner). 90-day check-ins later.
- J-D7 (owner). The building session releases ×5.
- J-D8 (design). Staging only: nothing reaches the employee record except through Add employee's own `send`.
  The HR person who presses Add is the proposer of the bank account.
- J-D9 (design). The board is a quiet board (steps strip + cards + drawer), not kanban columns.
- J-D10 (design). The welcome checklist does not start earlier (`pb.journey.case` needs an employee); Hiring's
  "Before they join" list stays the pre-day-one list.
- J-D11 (design). Insurance numbers, HR-only in Add employee's "Ask" mode, are optional inputs on the portal
  because HR checks everything before it lands.
- J-D12 (design). Recruiters see progress, never values or files.
- J-D13 (design). No card reading in this build; no new server packages.
- J-D14 (design). Sensitive values are write-only on the phone (masked after save).
- J-D15 (design). Device remembered 14 days after a correct code; link dies 14 days after the first day.

## 3. Gotchas inherited (read the source ledgers for detail)

| Ref | One line |
|---|---|
| F0 | The main checkout is 182 commits behind; build in a worktree from `origin/19.1`; cherry-pick `840036012` for the release script. |
| NH8 | Proposal payloads must be JSON-plain and are re-validated on replay. |
| NH39 | After `--test-enable` the server may not exit by itself; stop it after "post-tests". |
| NH56 | The ID-document category requires an expiry date. |
| NH57 | The bank request is created as the hire's sender. |
| NH58 | Hiring's legs swallow their failures — assert outcomes, not absence of errors. |
| NH71/78 | `.po` model terms fill `noupdate` rows. |
| NH86 | A word reused on a new view needs that view's occurrence added to the existing PO entry. |
| NH87 | `odoo-bin i18n export`; append to `.po` as text; never `polib.save`. |
| RC11 | A hub tab's `probe` hides it unless truthy; group changes need an `orm_signaling` bump. |
| RC13 | An act_window given to `doAction` needs `'views': [[False,'form']]`. |
| RC14 | Asset changes need the `/web/assets` purge + version bump + `orm_signaling_assets` (the release script does it). |
| RC30 | `update_field_translations` raises for inactive languages — filter seeds to installed languages. |
| RC41 | `noupdate="1"` records do not reload on upgrade; later changes need a migration. |
| RC49 | Public QWeb and mails call no private methods; pass plain values. |
| RC68/70 | Shared addons dir: a new dependency can break another database's registry. |
| RC72 | On public pages `display:` beats `[hidden]`. |
| RC92/93 | Candidate words live in `pb.hiring.message.template`, sent only via `_mail_candidate`; never write `False` to a translated field. |
| RC95 | Hooks are a `leg()` after `super()`; honour the silencer context keys. |
| — | `ic()` renders a tick for an unknown icon name — test that every name exists. |
| — | A toast is hidden behind an open drawer — show the message inline too. |
| — | QuietGlance/QuietSteps are `t-call` templates with mandatory `q`-prefixed params, not components. |
| — | Older public Hiring pages use `#4F46E5`; do not copy it. |
| — | Cron counts per database are recorded in `/opt/deploy-notes.md`; an upgrade can re-activate switched-off jobs on `payobook_template` — the release script snapshots and restores them. |

## 4. New gotchas found while building (append below as J-1, J-2, …)

- J-1. A local test server must match exactly one database. Six Hiring public-page checks returned HTTP 404 when two copies matched the filter. All six passed on the same code with an exact database filter.
- J-2. Owner ruling. HR and the recruiter handling the particular offer may show a one-use code. With the link and the code, either can act on the person's phone page. The recruiter drawer itself shows item names and states only.
- J-3. Owner ruling. The release script must restore the on/off setting of each previously existing scheduled job while preserving the new Joining job. Restoring just the old list of active IDs switches off every new job.
- J-4. This checkout has an addon literally named `addons`. Selecting it as the source directory for every module misses the root-level custom modules. The release wrapper also has to preserve the space in `WHO="Codex JOINING"` across SSH.
- J-5. The active web-server access logs include the request URI. Owner approved scoped redaction of joining secrets on the active sites. Framework access logs and CSRF rejection messages also include the path.
- J-6. Owner ruling. File a permanent identity card under “Identity card — no end date” with the same access as ID documents. The existing ID category requires an expiry date, and the Hiring fallback holds the file at its source. A Joining-only copy would be erased after the retention period.
- J-7. The live server has neither PyMuPDF nor Poppler's PDF page renderer. Use “Open the paper” and require the paper to have been opened before signing.
- J-8. The local asset compiler evaluates CSS `max()` as a Sass numeric function. Use `calc(12px + env(safe-area-inset-bottom, 0px))` for the phone footer.
- J-9. All five sites use the framework's seven-day idle session default. Owner approved a separate, signed, host-only Joining device cookie. It expires 14 days from the original code check, is restricted to that joining link and only restores that joining's session entry on its landing page.
- J-10. Eager public rendering returns markup. Materialise the normal response with `flatten()` before setting the privacy headers. The website also owns the QWeb name `editable`. Using it for section permission silently hides Save from the person completing the form.
- J-11. Joining uses the shared filter kit's deferred load so its initial “Ready for you to check” filter is applied before the first page. Loading the kit and setting the filter concurrently can restore an older filter over it.
- J-12. Close and review actions must account for a pending save. In Chrome, closing before a first-day edit finished could reopen the drawer when the reply arrived.
- J-13. The shared candidate sender can render the same company template for an invited person with no applicant. Pass the date as a language-aware token so the weekday follows the actual email language.
- J-14. Add employee can create and approve the proposal in one call. Claim the checked joining on the proposal before approval runs. A returned or withdrawn proposal releases the claim so HR can send the hire again.
- J-15. The welcome runner isolates each document-filing step. A Joining hire must complete both filing steps before it can become Ready for day one. Otherwise a temporary filing failure could allow the original to be erased with the staging details.
- J-16. A card Hiring already holds needs its accepted end date passed through the existing Hiring date field. A permanent card needs a separate copy in the permanent ID category.
- J-17. Load the existing Welcome options before selecting the first studio step. A company-required field such as a shuttle route only becomes known when those options arrive.
- J-18. A signed PDF can have the right number of pages and still miss its headings. The signing page uses its own print styling. Verify the person's name, paper title, original fingerprint and signature image in the rendered file.
