# SUDIMA Phase D — AI Bank Account Validation (OCR + Approval Workflow)

**Scope item:** Sudima demo requirement **#3 AI Bank Account Validation** (*Not Built* — the scope's headline "AI" moment): upload bank document → AI/OCR field extraction → automated validation (format, duplicates, name similarity) → **Employee → HR → Finance → update employee master**, with full version history.
**Modules:** NEW `biz_doc_ocr` (generic engine) + NEW `pb_bank_ocr` (overlay) + **additive** provider work inside `pb_payroll_ai_insights`.
**Ledger:** `docs/FORMULA_ENGINE_CONVENTIONS.md` — **C1, C2, C18 binding** (C18.1 engine/overlay, C18.6 provider-vision contract).
**Prerequisites:** Phase C shipped (`biz_approval_chain` exists; sidebar `scan` icon exists from Phase A).

---

## 1. Scope

1. **Multi-provider vision layer** (client-selectable, locked decision): **Claude API (anthropic), OpenAI, Ollama (local), Tesseract (offline OCR)** — added additively to the existing `pb_payroll_ai_insights` provider abstraction — plus a **deterministic parser layer that always runs** and doubles as the no-AI fallback.
2. **`biz_doc_ocr`**: generic schema-driven document field-extraction service + drag-drop upload widget + retry cron. Reusable for invoices, ID cards, contracts.
3. **`pb_bank_ocr`**: the bank-change request lifecycle — upload (Bank Confirmation Letter / Statement / Passbook / Cancelled Cheque), extraction (bank, branch, holder name, account number, IBAN, SWIFT), validation engine (format, registry normalization, duplicate detection, name string-similarity, variance flags), 3-tier approval chain, versioned write to the employee master.

### Binding non-goals
- **`OpenAIProvider` must not be modified** except adding the vision method; existing insights features must be regression-free.
- **NO new AI config model** — extend `payroll.ai.config` (selection_add + `purpose`).
- **NO auto-approval and NO auto-reject**: AI/similarity results are advisory; humans decide at every tier. A low name-match NEVER blocks by itself.
- **NO `queue_job`/external queue dependency** — sync-with-progress + retry cron.
- **NO `res.partner.bank` migration** — the system of record stays the four `hr.employee.vietnam_bank_*` Chars (a migration is a separate product decision).
- **NO rapidfuzz/pip additions for similarity** — stdlib `difflib` only. (Provider SDKs: `anthropic` may be pip-installed on the server; `ollama` uses plain `requests`; `pytesseract`+binary optional — ALL guarded imports, C18.6.)

---

## 2. Verified plumbing facts (do not re-derive)

- ✓ **Provider layer** (`pb_payroll_ai_insights`): `payroll.ai.config` (`models/payroll_ai_config.py:11-166`) — `provider_type` Selection (openai only), `api_key` (sanitized on write — invisible-unicode strip), `model_name` default gpt-4o-mini, `base_url`, `timeout`, `max_tokens`, `temperature`, `is_active`, `company_id`. `BaseAIProvider` (`ai_providers/base_provider.py:10-141`) — `generate_text` is the abstract core (`:20-33`); JSON-parsing fallback handles ```-fenced output. `OpenAIProvider` (`ai_providers/openai_provider.py:10-150`) — `openai` SDK, `_client` cached. **`PROVIDER_REGISTRY = {'openai': OpenAIProvider}` at `ai_providers/provider_factory.py:9-11`.** `test_connection()` exists (latency echo). **No vision anywhere.**
- ✓ **Chain engine**: `biz_approval_chain` from Phase C (`biz.approval.chain.mixin`, `biz.approval.step.log`, `ApprovalStepper` widget) — see that handover §3.1.
- ✓ **Audit precedent**: `contract.component.change` (`pb_hr_payroll_formula/models/contract_component_change.py:6-67`).
- ✓ **Bank fields**: `hr.employee.vietnam_bank_name / vietnam_bank_branch / vietnam_bank_account_number / vietnam_bank_account_name` (plain Chars, `pb_hr_payroll_vietnam/models/hr_employee_vietnam.py`); consumed by `vietnam_bank_export_wizard.py` (`pb_hr_payroll_vietnam/wizards/`, formats vietcombank|bidv|techcombank|mb_bank|generic). No approval/versioning exists on these fields today.
- ✓ **LLM entry-point convention (C1)**: engine-side code reaches the LLM only guarded + with deterministic fallback (pattern `multisheet_import_preview.py:206-213`).
- ✓ **Attachments**: no bespoke drag-drop component exists — build one in `biz_doc_ocr` (plain `ir.attachment` create, base64).
- ✓ Cockpit/sidebar/theming as Phase A §2; VU form pattern for record forms as Phase C §2.
- ✓ VN context: account numbers are bank-specific 6–19 digit strings (no national IBAN scheme; IBAN field stays optional/blank for VN docs); SWIFT/BIC format `^[A-Z]{4}VN[A-Z0-9]{2}([A-Z0-9]{3})?$` for VN banks, generic `^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$` otherwise.

---

## 3. Architecture

### 3.1 Provider work (inside `pb_payroll_ai_insights` — additive only)

- **`BaseAIProvider`** gains (non-abstract, C18.6):
  ```python
  def supports_vision(self) -> bool: return False
  def generate_vision(self, prompt, images, max_tokens=1500, **kw):
      """images: list of {'mime': 'image/png'|'image/jpeg'|'application/pdf', 'data_b64': str}
      Returns raw text (caller parses)."""
      raise NotImplementedError
  ```
- **`anthropic_provider.py`** — guarded `import anthropic`; messages API; vision via base64 image blocks (PDFs: document block); `generate_text/chat` implemented too; default model `claude-sonnet-5` (config-overridable); `supports_vision` True.
- **`ollama_provider.py`** — NO SDK: `requests.post(f"{base_url}/api/chat", json={model, messages, images, stream:False}, timeout)`; default `base_url` `http://localhost:11434`, default model `llava` (docstring: qwen-vl also works); `supports_vision` True; `is_available` = one cheap `GET {base_url}/api/tags` with short timeout.
- **`tesseract_provider.py`** — guarded `import pytesseract, PIL`; `generate_vision` = raw OCR text of each image concatenated (`lang='vie+eng'` if the `vie` traineddata is present, else `eng` — detect via `get_languages`); `generate_text/chat` raise NotImplementedError; `supports_vision` True; `is_available` checks the binary.
- **Registry**: add all three to `PROVIDER_REGISTRY`. **Do not touch `OpenAIProvider`** except: add `generate_vision` (chat.completions with `image_url` data-URI content parts) + `supports_vision` True.
- **`payroll.ai.config`**: `selection_add=[('anthropic','Anthropic Claude'),('ollama','Ollama (local)'),('tesseract','Tesseract OCR')]` with `ondelete='cascade'` per key, + new field `purpose` Selection `[('insights','AI Insights'),('doc_ocr','Document OCR')]` default `insights`. Resolution helper `@api.model get_provider(purpose)` → active config with that purpose, else any active config, else None. (`doc_ocr`, not `bank_ocr` — the engine is generic.)

### 3.2 `biz_doc_ocr` — generic engine (depends: `base`, `web`, `pb_payroll_ai_insights`)

```
biz_doc_ocr/
├── models/biz_doc_ocr.py      biz.doc.ocr AbstractModel service + biz.doc.ocr.job
├── data/cron.xml              retry cron (*/5 min)
└── static/src/ js/doc_drop.js|xml|scss   DocDrop upload widget (--bdo-* props)
```

- **`biz.doc.ocr` service** — `extract(schema, attachment_ids, post_processor=None)`:
  - `schema` = `{'fields': [{'name','label','type': 'char|digits|code', 'hint'}], 'doc_kinds': [...]}`.
  - Pipeline: resolve provider (`purpose='doc_ocr'`) → if `supports_vision()`: build a STRICT-JSON prompt from the schema (+ per-field `confidence` 0–1 and a `doc_kind` guess), call `generate_vision`, parse via the base-provider JSON fallback → normalize into `{'fields': {name: {'value','confidence'}}, 'doc_kind', 'raw_text', 'provider'}`.
  - Tesseract path (vision-capable but returns prose): run OCR, then hand `raw_text` to the `post_processor` callable for field extraction (deterministic).
  - `post_processor(result_dict) → result_dict` always runs last when provided (normalization/validation layer).
  - **No provider / provider down** → result with empty fields + `provider:'none'`, `error` — callers must degrade gracefully (C1 fallback doctrine).
- **`biz.doc.ocr.job`**: `res_model/res_id`, `state pending|running|done|failed`, `attempts` (≤3), `payload/result` Text-JSON, `error`. Sync path: caller creates job `running`, runs inline, stores result. Retry cron picks `pending|failed(attempts<3)` — covers slow local Ollama/Tesseract and API blips.
- **`DocDrop` widget**: drag-drop / tap-to-browse → base64 → callback with `{name, mime, data}`; preview thumbnail; jpg/png/pdf only, ≤ 10 MB; `--bdo-*` styling props; no Payobook imports.

### 3.3 `pb_bank_ocr` — overlay (depends: `biz_doc_ocr`, `biz_approval_chain`, `pb_hr_payroll_vietnam`, `pb_sidebar`, `pb_import_kit`)

**Models**
- **`pb.bank.change.request`** (`mail.thread`, `biz.approval.chain.mixin`):
  - `name` seq `BCR/2026/0001`, `employee_id` required, `attachment_id` m2o ir.attachment required, `doc_kind` Selection (confirmation_letter|statement|passbook|cheque|other — from OCR guess, editable)
  - `state`: `draft → submitted → hr_review → finance_review → approved | refused` — transitions: draft→submitted (owner/HR), submitted→hr_review is **automatic on submit** (skip: model the chain as `draft → hr_review → finance_review → approved`, submit = draft→hr_review by owner; simpler and matches scope's Employee→HR→Finance→Update), gates: hr_review→finance_review (`om_hr_payroll.group_hr_payroll_user` HR tier), finance_review→approved (finance group — same `env.ref` fallback chain as Phase C tier 3)
  - `ocr_state` pending|running|done|failed + `ocr_provider`, `ocr_raw` Text
  - Extracted: `x_bank_name, x_bank_branch, x_account_name, x_account_number, x_iban, x_swift` + `confidence_json`
  - Snapshot at submit: `cur_bank_name, cur_bank_branch, cur_account_name, cur_account_number` (readonly copies of the employee's current values — the diff basis)
  - Validation results (computed, stored on demand via `action_validate()`): `v_format_ok` + `v_format_msg` (account digits-only 6–19; SWIFT regex §2; bank name resolved against dictionary), `name_match_score` Float 0–100, `name_match_band` Selection green(≥85)|amber(60–85)|red(<60), `duplicate_ids` m2m to employees sharing the normalized account+bank, `duplicate_ack` Boolean (HR must tick when duplicates exist)
- **Deterministic VN layer** (`models/vn_bank_dictionary.py` + data): ~40 VN banks as `pb.bank.registry` records (`name`, `short_name`, `swift_prefix`, `aliases` — e.g. Vietcombank/VCB/Ngân hàng Ngoại thương; Techcombank/TCB; BIDV; VietinBank/CTG; ACB; MB/MBBank; Agribank; VPBank; Sacombank/STB; TPBank; SHB; HDBank; OCB; SeABank; VIB; Eximbank/EIB; MSB; LPBank; PVcomBank; BacABank; NamABank; ABBank; VietABank; KienlongBank; NCB; PGBank; SaigonBank; CIMB VN; UOB VN; Shinhan VN; Woori VN; HSBC VN; SCB; DongABank; BaoVietBank; VietBank; CBBank; GPBank; OceanBank; Public Bank VN — data file, editable). Post-processor: fold diacritics (`unicodedata.normalize('NFD')` strip combining marks) + uppercase → match/normalize bank name, regex account number from raw text (longest 6–19 digit run) when the provider missed it, uppercase SWIFT.
  - **Name similarity**: `difflib.SequenceMatcher(None, fold(a), fold(b)).ratio()*100` between `x_account_name` and employee's `name` (and `vietnam_bank_account_name` if set — take the max).
- **`pb.employee.bank.history`** (clone `contract.component.change` shape): `employee_id`, old/new × 4 fields, `change_source` Selection `ocr_request|manual`, `request_id`, `changed_by/at` readonly defaults. Plus `hr.employee.write()` override (in this module): when any `vietnam_bank_*` changes WITHOUT the context flag `from_bank_request`, log a `manual` history row.
- **Approve hook** `_after_approval_transition('approved')`: with `from_bank_request` context, write the 4 fields to the employee, create the `ocr_request` history row — one atomic transaction.

**Flow**: cockpit upload (DocDrop) → create request draft + `action_run_ocr` immediately (inline; scan-shimmer UI covers 3–8 s) → extraction lands in `x_*` + confidences → user verifies/corrects fields side-by-side with the document → `action_validate()` (format/dup/name) → submit → HR queue → Finance queue → approved = master updated + history.

**Cockpit** (tag `pb_bank_ocr`, AbstractModel `pb.bank.ocr.get_queue_data()`): queues (Mine / HR review / Finance review / Done), KPIs, the split-view request screen (OWL — this one IS a bespoke screen, not a native form: document viewer left, fields right), settings card exposing the `purpose='doc_ocr'` provider chip + `test_connection` button. Sidebar item "Bank Verification" (icon `scan`), gated `om_hr_payroll.group_hr_payroll_user`; employees reach their own requests through the request screen only (record rule: own or HR/finance groups).

---

## 4. WOW-UX specification

1. **Upload + scan moment** (the demo's AI beat): full-width DocDrop zone → on run, the document preview gets a top-to-bottom **scan shimmer line** (CSS animation, `--pbim-primary` glow) while a right-side skeleton fills field-by-field as results land; each field materializes with its **confidence pill** (green ≥ 0.9 / amber ≥ 0.6 / rose below, showing %).
2. **Split verify view**: left = zoomable document (wheel zoom + drag pan, plain CSS transform); right = extracted fields, each editable with the confidence pill and a small "from document" tag that flips to "edited" on change.
3. **Diff & verify card**: two-column "Current on file → Extracted" with per-field change highlighting (unchanged grey, changed `--pbim-primary-light` wash); **name-match gauge** (semi-circular, green/amber/rose bands, needle at score); **duplicate banner** (rose, full width) listing the colliding employees with an explicit "I have verified this is not a duplicate payment target" checkbox for HR.
4. **Approval queues**: HR and Finance lanes with count badges; request rows show employee, bank chip (normalized short_name), masked account (`•••• 4321`), scores; `ApprovalStepper` on the request screen (Employee → HR → Finance → Master updated).
5. **History timeline drawer** (per employee, reachable from the request and from People): vertical timeline of bank changes — source icon (scan = OCR request, pencil = manual), old→new masked accounts, actor + timestamp.
6. **Settings card**: provider chip row (Claude / OpenAI / Ollama / Tesseract — active one filled), model name, latency from last `test_connection`, and a "deterministic fallback always on" note.

---

## 5. Safety rails

1. **Human-in-the-loop absolutes**: no state advances without a user click; extraction/validation never auto-writes the employee master; only the finance-tier approval does, atomically, via the context-flagged path.
2. **Least privilege**: employees see only their own requests (record rule); account numbers render **masked** everywhere except the split verify view for HR/finance; attachments inherit request ACLs.
3. **API keys**: reuse `payroll.ai.config` storage (existing sanitization); never log keys or raw base64; log provider + latency + confidence only.
4. **Guarded imports everywhere** (C18.6): a server without `anthropic`/`pytesseract` installs and runs — those providers just report `is_available() == False`; the settings card shows why.
5. **Regression freeze on insights**: existing `openai` `purpose='insights'` config keeps working untouched; run the insights chat smoke test post-deploy.
6. **PDF handling**: Anthropic accepts PDFs natively; OpenAI/Ollama/Tesseract need page-to-image — if `pdf2image`/poppler is absent, reject PDFs for those providers with a clear message rather than half-working (report-back which path live supports).
7. **Duplicate ack is required** to submit when `duplicate_ids` non-empty; refusals require a note (chain mixin).
8. Multi-company scoping on requests/history/registry; i18n EN/VI.

---

## 6. Test cases

**Server:**
1. Registry: `get_provider('doc_ocr')` returns the purposed config; falls back to any active; None-safe when nothing configured (extract returns the degraded result, no traceback).
2. Vision contract: mock provider returning fenced JSON → parsed fields + confidences normalized; malformed JSON → `failed` job with error, retry cron re-attempts ≤ 3.
3. Tesseract path: fixture PNG of a typed bank letter (commit a small test asset) → post-processor pulls a 10-digit account + normalizes "NGAN HANG TMCP NGOAI THUONG" → Vietcombank.
4. Deterministic layer: diacritics fold ("Nguyễn Văn Á" ≡ "NGUYEN VAN A" → 100), amber band at a one-token difference, red at a different person.
5. Duplicate detection: second employee with same normalized account+bank → `duplicate_ids` set; submit blocked until `duplicate_ack`.
6. Format validation: 5-digit account fails, 12-digit passes; `BFTVVNVX` passes SWIFT, `BFTV1234` fails.
7. Chain: draft→hr_review by owner; hr_review→finance_review requires HR group; finance→approved requires finance group; approved writes the 4 employee fields + ONE `ocr_request` history row; refuse at finance leaves master untouched.
8. Manual-edit audit: writing `vietnam_bank_account_number` directly on the employee (no context flag) creates a `manual` history row; the request path creates none extra.
9. Bank export wizard still exports the (new) account values correctly post-approval.
10. Insights regression: existing insights provider call path unchanged (unit-level: factory returns OpenAIProvider for the insights config; chat smoke on live).

**Chrome MCP:**
11. Cockpit upload of a sample bank-letter image → scan shimmer → fields + confidence pills appear; correct one field → "edited" tag.
12. Diff card shows current→extracted highlighting; name gauge renders in the right band for a matching name.
13. Full approval walk (employee user → HR → finance/Mitchell Admin): stepper fills, final toast, employee form shows new bank fields, history drawer shows the entry (screenshots: split view, diff card, history drawer).
14. Duplicate scenario: banner + forced ack checkbox.
15. Settings card: provider chips render; `test_connection` on the active provider returns latency; switch active provider config (e.g. to tesseract) and re-run an extraction end-to-end.

---

## 7. Deploy & verify

Memory `payobook-deploy` ritual. `-i biz_doc_ocr,pb_bank_ocr -u pb_payroll_ai_insights,pb_sidebar`. Never `-u pb_hr_payroll_formula`. Pip on live (PEP668): `sudo python3 -m pip install --break-system-packages anthropic` (+ optionally `pytesseract` and `apt install tesseract-ocr tesseract-ocr-vie` if the offline demo path is wanted — report what was installed). Configure a `doc_ocr` `payroll.ai.config` on live (provider per available key; Tesseract as the keyless fallback). Bump versions (C2). Chrome-MCP verify §6.11-15; insights chat smoke test.

---

## 8. Report back

1. Tests 1–15 results + the three §6.13 screenshots.
2. What was pip/apt-installed on live and which providers report `is_available()` there; which provider the demo config uses; PDF support outcome per provider (§5.6).
3. Median extraction latency + a confidence-quality note per tested provider on the sample documents.
4. Deviations (what + why), file list, manifest versions.
5. New gotchas → proposed C18 addendum wording.
6. Proof the insights path is regression-free (smoke result) and `OpenAIProvider` diff is vision-only.

---

## Kickoff line (paste into the Opus session)

> Read `docs/handovers/SUDIMA_PHASE_D_BANK_OCR.md` and `docs/FORMULA_ENGINE_CONVENTIONS.md` (C1, C2, C18 binding), then implement Phase D exactly as specified: additive vision providers in `pb_payroll_ai_insights`, new `biz_doc_ocr` + `pb_bank_ocr`, tests §6, live deploy §7. Report back with the six numbered items in §8. Never auto-write the employee master from AI output — only the finance-tier approval does, atomically, with history.
