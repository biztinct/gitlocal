# JOINING — design specification

**What this is.** The complete experience and screen design for the Joining portal: a person whose offer is
signed fills in their own details on their phone before day one; HR checks them on a Joining board; Add employee
arrives filled in. Owner-approved 2026-11-27.

**Read with:** the clickable prototype `docs/design/joining-portal-poc.html` (open it in a browser; published at
https://claude.ai/artifact/8DGjzWnqWkcTKprJ618AnK), `JOINING_FACTS.md` (plumbing), `JOINING_BUILD_HANDOVER.md`
(architecture, phases, tests, release), `JOINING_LEDGER.md` (rules and gotchas).

**Precedence.** The prototype shows look, tone, flow and wording. **Where the prototype and this document
differ, this document wins** (§11 lists every difference). Where this document and existing product behaviour
differ on something this document does not mention, existing behaviour wins.

---

## 1. Owner decisions (binding)

| # | Decision | Date |
|---|---|---|
| O1 | The portal opens with a **one-time code**, no password, no account. This reverses NEWHIRE ledger D8. | 2026-11-27 |
| O2 | The code goes **by email where the site can send email; everywhere HR can also "Copy link" and "Show code"** and pass them on by WhatsApp or phone themselves. No SMS/WhatsApp sending by the system. | 2026-11-27 |
| O3 | The **Joining board appears inside Hiring and inside People** — one board, two doors. | 2026-11-27 |
| O4 | Papers are signed by **drawing a signature with a finger**, saved with the paper plus name, date and time. | 2026-11-27 |
| O5 | People hired outside Hiring get the same portal through **"Invite someone"** on the board. | 2026-11-27 |
| O6 | 7/30/60/90-day check-ins and the trial-period reminder are **later** — not in this build. | 2026-11-27 |
| O7 | The building session **also releases** to all five sites. | 2026-11-27 |
| O8 | Kept from today: second-person approval of the hire and of the bank account. HR checks everything before it reaches the employee record. | standing |

## 2. Principles

1. **Never asked twice.** What Hiring or the offer knows (name, contact, role, manager, wage, first day, papers
   already uploaded) is shown as already held, never asked again.
2. **HR checks, HR does not type.** Nothing the person sends touches the employee record until HR accepts it and
   presses Add in the existing Add employee screen.
3. **One definition of what is asked.** The portal's fields are the Add employee step-5 catalogue for the
   person's Country of work. No second list anywhere.
4. **The person can stop and come back.** Every section saves on its own. A missing bank account never blocks
   the rest.
5. **Show only what is due.** One section at a time; first-day content appears, it is not a wall of tasks.
6. **Works when email is off.** Every email-dependent step has an HR-passes-it-on twin on the board.
7. **Premium and calm.** Same indigo system as the product; generous spacing; one primary button per screen;
   Lucide line icons; no emoji; no gradients; plain words a first-time employee understands.

## 3. Vocabulary (use exactly these words on screen)

| Word | Meaning |
|---|---|
| **Joining** | The tab and board (before day one). Not "onboarding", not "pre-boarding". |
| **Joiners** | The existing People tab for after day one. Unchanged. |
| **joining link** | The link sent to the person. |
| **code** | The 6-digit one-time code. Never "OTP", "PIN", "token". |
| **Invited / Filling in / Ready for you to check / Ready for day one** | The four board steps. |
| **Accept / Send back** | HR's two actions on an item. |
| **Add as employee** | Opens Add employee. |
| **Country of work**, **pay scheme**, **first day**, **trial period** | As already used in Add employee. |
| **identity card**, **tax number**, **bank account**, **emergency contact**, **papers** | Item words; the exact per-country labels come from the catalogue. |

Never on screen: "Odoo", "token", "OTP", "staging", "portal user", "record", "payload", "onboarding", internal
codes. The product is "Payobook"; the employer is the company's own name.

## 4. The journey

```
Offer signed in Hiring ──► joining record made, link sent (or waiting for HR to pass on)      [Invited]
        │                        "Invite someone" on the board makes the same record
        ▼
Person opens link ► enters code ► welcome ► fills sections, signs ► Send to HR                 [Filling in]
        │   reminders every 3 days · HR nudged when it stalls · "at risk" inside 7 days
        ▼
HR opens the card ► Accept / Send back each item ► Add as employee                             [Ready for you to check]
        │   sent-back items reopen on the phone; the card returns to Filling in
        ▼
Add employee opens with step 5 filled from the person ► Check and add ► usual approvals        [Ready for day one]
        │
        ▼
Day one: the same link shows the first-day plan. After that the existing Joiners board,
welcome checklist and My Payobook take over, unchanged.
```

## 5. What the person is asked (sections)

The portal groups the step-5 catalogue items for the joining's Country of work into sections. A section appears
only if it has at least one item for that country.

| # | Section title | Catalogue items | Notes |
|---|---|---|---|
| 1 | **About you** | `personal` | Shows name, email, phone from Hiring as "We already have this". Asks date of birth, gender, home address, city, mobile. |
| 2 | **Your identity card** | `id_number` + its merged ID paper | Number typed; photo of the card (front; optional second file); "Valid until" date, with "No end date" tick. |
| 3 | **Bank account** | `bank` | "Bank account in" country chooser (defaults to Country of work); fields from the bank format; "I do not have it with me. Remind me later". |
| 4 | **Tax and social insurance** | `tax_number` (+ merged tax paper), `tax_status` / `tax_regime` / `tax_fund`, `insurance` | Every number has "I do not have one yet" → left for HR. Insurance numbers are optional ("only if you already have one"). |
| 5 | **Emergency contact** | `emergency` | Name and phone. |
| 6 | **Your papers** | every `paper-<category>` item of that country not merged above | One upload row per paper. Papers Hiring already holds show "We already have this from your application" and are not asked. |
| 7 | **Sign your papers** | the company's papers to sign (§7.6) | Hidden when the company has none. |
| 8 | **Your first day** | information + the laptop question when Hiring asked one | Always last. |

Rules:
- **Required to send:** sections 1, 2, 4, 5, 7 complete; section 3 complete **or** "Remind me later"; section 6
  — papers the catalogue marks needed for first pay or joining are required, others optional; section 8 opened
  once. "I do not have one yet" on a tax or insurance number counts as complete.
- **Country with no catalogue support** (anything outside VN/ID/IN/SG, e.g. MY/TH/KH/AU/NZ): sections 1, 2 (ID
  number + paper if the catalogue has one), 3 (bank format for that country, else "other"), 5, 6, 7, 8.
  Section 4 is hidden. No invented tax fields.
- Field labels, hints, option lists and validation come from the catalogue and the bank format — the portal
  renders them, it does not define them.

## 6. Design language

### 6.1 Tokens (identical in the back office and on the phone)

| Role | Value | Back-office token |
|---|---|---|
| Primary | `#5A4BB0` | `--pbim-primary` |
| Primary hover | `#4A3D96` | `--pbim-primary-hover` |
| Primary soft (tints, selected, hello card) | `#EDEAF8` | `--pbim-soft` |
| Primary light (soft borders) | `#CBC2EE` | — |
| Ink | `#1E1B2E` | `--pbim-ink` |
| Muted text | `#64748B` | `--pbim-muted` |
| Faint text / labels | `#94A0B4` | — |
| Line | `#E2E8F0` | `--pbim-line` |
| Line 2 | `#EEF0F6` | `--pbim-line-2` |
| Canvas | `#F4F5FB` (phone) / product bg | `--pbim-bg` |
| Card | `#FFFFFF` | — |
| OK / done | `#2E7D4F` on `#E4F3EA` | green + soft |
| Waiting / later | `#B45309` on `#FDF1DD` | amber + soft |
| Problem / at risk | `#DC2668` on `#FCE7EF` | rose + soft |
| From the new person | `#0F8B8D` on `#E0F2F2` | teal + soft |
| Radius | cards 14px, inputs/buttons 10px, pills 999px | `--pbim-r*` |
| Shadow | `0 1px 2px rgba(30,27,46,.05), 0 8px 24px rgba(30,27,46,.06)` | `--pbim-sh` |
| Fonts | Inter (body, 14px/1.5); Manrope 700/800 for headings (as Add employee does) | |

- The back office uses the `--pbim-*` variables and `.pbim-*` classes; never a literal colour there.
- The public phone pages use the literal values above (public pages cannot rely on back-office variables).
  Do **not** reuse the older public pages' `#4F46E5`.
- Single light theme, as the product.

### 6.2 Components

- **Buttons:** one solid primary per screen (`.pbim-btn.primary` / phone `.pbjp-btn--pri`); everything else
  outline or ghost. Danger = rose text, never a red fill. Height ≥ 44px on the phone.
- **Chips** for state: OK green, waiting amber, problem rose, "from the person" teal, "from Hiring" indigo soft,
  neutral grey. Chip = icon (12px) + 2–4 words.
- **Source chips** (where a value came from): `From Hiring` (indigo), `From the signed offer` (indigo),
  `From {first name}` (teal), `Read from Hiring's paper` (grey). Reuse `pbnh-chip` variants in the studio.
- **Icons:** Lucide only, 2px stroke, round caps. Back office through `ic()`; phone pages through an inline
  `<svg>` set. Names used: `userPlus, user, idCard, landmark (bank), receipt (tax), heart, pen, sun, camera,
  lock, clock, alertTriangle, send, check, x, arrowLeft, arrowRight, eye, bell, copy, keyRound, layers,
  briefcase, mapPin, phone`. Add any that `IC` lacks (an unknown name renders a tick — test for it).
- **Progress:** phone = 56px ring with % in the centre + "n of m done"; board card = 6px bar + %.
- **Empty states:** icon tile, one `h2`, one sentence, one button (the product's `pbim-empty` pattern).
- **Motion:** 150ms colour transitions, 400ms progress-bar width; nothing else. Honour
  `prefers-reduced-motion`.
- **Focus:** visible 2px primary outline, 2px offset, on every control.

### 6.3 Writing

Short sentences. Say what happens. Address the person as "you". Dates as "Monday 14 December". No exclamation
marks. Errors say what is wrong and how to fix it ("That code is not right. You have 3 tries left."). English
strings below are the source; Vietnamese and Indonesian ship with the build.

---

## 7. The phone (public pages)

Mobile-first at 360px; centred column max 480px on larger screens with the canvas colour around it. Every page
has the same chrome:

- **Top bar** (white, 1px bottom line, 56px): left = back arrow on section pages, otherwise the company logo
  (or a 28px soft tile with the `sun` icon); centre-left = page title (Manrope 700, 15px); right = "Saved" green
  chip after any save on this visit, and on the welcome and hub pages a language control (§7.9).
- **Body:** 16px gutters, 12px gaps between blocks.
- **Footer bar** (white, 1px top line, sticky bottom, safe-area aware): the primary button, full width; an
  optional ghost button under it.

### 7.1 Link states (one page, one look)

| State | When | What shows |
|---|---|---|
| Not found | bad or unknown link | Soft tile `lock`, **"This link is not active"**, "Ask the person who sent it for a new one." Same page for unknown, withdrawn and expired links. |
| Closed | the joining was cancelled / did not join | Same as Not found. |
| Code | link good, device not yet confirmed | §7.2 |
| Welcome | confirmed, nothing saved yet | §7.3 |
| Hub | confirmed, at least one visit past welcome | §7.4 |
| Sent | everything sent to HR | §7.8 |
| Day one | the person has been added as an employee | §7.8, day-one variant |

The link stops working 14 days after the first day, or 30 days after the joining is cancelled.

### 7.2 Code screen

- Hello card (primary soft, 16px radius): eyebrow chip `lock` **"One quick check"**; `h2` **"Enter your code"**.
- Sentence, one of:
  - email sent: "We sent a 6-digit code to **d•••@gmail.com**. It works for 10 minutes."
  - no email possible: "Enter the 6-digit code **{HR contact first name}** gave you."
- Six single-digit boxes (numeric keypad, `autocomplete="one-time-code"`, paste fills all six, auto-advance,
  auto-submit on the sixth digit). Without script it is one input.
- Primary: **"Continue"**.
- Ghost, email case only: **"Send me a new code"** (disabled with a countdown "You can ask again in 0:42").
  No-email case: plain text "No code? Ask {HR contact name} to show you a new one."
- Errors (inline, rose, under the boxes):
  - wrong: "That code is not right. You have {n} tries left."
  - expired: "That code has run out. Ask for a new one."
  - locked: "Too many tries. Wait 15 minutes, then ask for a new code."
- After success this device is remembered for 14 days; the person is not asked again on it.
- Small print under the card: "This page is only for {full name}. If that is not you, close it."

### 7.3 Welcome

- Hello card: chip `lock` **"Opened with your code"**; `h2` **"Welcome to {company}, {first name}"**; line
  "You start as **{job title}** on **{Monday 14 December}**, in {17} days." (0 days → "today"; past → omit the
  count).
- Manager note card (only if a note exists, §8.5): avatar initials, "**{manager name}**, your manager", the
  note in quotes.
- Plain note (dashed border): "**About 10 minutes.** You can stop at any point and come back with the same
  link. Have your identity card, tax card and bank details nearby."
- Language control (§7.9).
- Footer primary: **"Start"** → hub.

### 7.4 Hub ("Before you join")

- Progress card: ring with %, "**{n} of {m} done**", sub "Saved as you go. You start in {17} days."
- If HR sent something back: an amber card above the list — `alertTriangle` "**{HR first name} asked you to
  fix {n} thing(s)**" and the first note; tapping goes to the first such section.
- One row per section (§5): 36px icon tile, title, sub-line, whole row tappable.
  - not started: section icon on soft indigo; sub = a hint ("1 minute", "Take a photo and type the number",
    "Where your pay goes", "Numbers you already have", "2 papers", "When, where, what to bring").
  - done: green `check` tile; sub "Done".
  - later: amber `clock` tile; sub "To finish later".
  - sent back: rose `alertTriangle` tile; sub = HR's note (one line, truncated).
  - accepted by HR (after sending): green tile; sub "Checked by HR"; row opens read-only.
- Footer primary: `send` **"Send to HR"** — disabled until the required rules of §5 are met; under it, when
  disabled, a muted line naming what is missing ("Still needed: Your identity card, Sign your papers").

### 7.5 Section pages

Common: title in the top bar with back arrow (back = hub, anything typed is kept as a draft of that section);
an intro sentence; the fields; footer primary **"Save and continue"** → saves, returns to the hub, focuses the
next not-done row.

- **Fields:** label above (12px, 600, muted), input 44px, 10px radius; hint below in faint text; error below in
  rose with the input border rose. Selection lists are native selects. Dates are native date inputs. Numeric
  IDs use `inputmode="numeric"` where the catalogue's rule is digits-only.
- **Sensitive values** (identity number, tax and insurance numbers, bank account number): once saved they
  re-display **masked** ("•••• •••• 0003") with a **"Change"** link that clears the field for retyping. The page
  never sends a saved sensitive value back in full.
- **Validation** is the catalogue's and the bank format's own, run on the server on save; the message is the
  catalogue's message, shown under the field. Nothing is saved from a section that has an error.
- **"We already have this" block** (dashed): `check` "**We already have** your name, email and phone from your
  application. You will not be asked again." (About you); for papers: "We already have this from your
  application."

Per section:

1. **About you** — block above; then date of birth, gender, home address, city, mobile (prefilled from Hiring's
   phone, editable).
2. **Your identity card** — intro "{card label}. Lay it flat in good light." Upload tile (dashed, primary soft,
   `camera`): **"Take a photo of your card"** (opens the camera on a phone; a file chooser elsewhere); after
   upload shows a thumbnail row with file name, size, **"Replace"**. Then the number field (label from the
   catalogue), "Valid until" date, tick "My card has no end date". Second optional upload "Back of the card".
3. **Bank account** — intro "Your pay is sent here. The name on the account must match your identity card."
   "Bank account in" select; fields per the bank format (bank chooser with search where the format has a
   directory; account number; account holder, prefilled with the full name; IFSC / bank code / branch code /
   BSB / SWIFT as the format says). Ghost under the primary: **"I do not have it with me. Remind me later"** →
   marks the section "To finish later".
4. **Tax and social insurance** — intro "These are the numbers {country} asks for. Leave any you do not have
   yet; HR will help you get one." Each number: field + tick "I do not have one yet". Tax status / regime / fund
   as a select with the catalogue's options and hint. Insurance numbers under a sub-heading "Only if you already
   have one". Tax-card photo upload where the catalogue merges a tax paper.
5. **Emergency contact** — "Who should we call if something happens at work?" Name, phone.
6. **Your papers** — one card per paper: name, why ("Needed before your first pay" / "Needed when you join" /
   "If you have it"), upload row, issue date / "Valid until" where the category needs them.
7. **Sign your papers** — §7.6.
8. **Your first day** — §7.7.

Uploads: photo (JPEG/PNG) or PDF, up to 10 MB each. Photos are downscaled in the browser to 2,000px on the long
side before upload. Progress shows inside the tile; failure message "That file did not upload. Try again, or
use a smaller photo."

### 7.6 Sign your papers

- List of papers, each a row: `receipt` icon, name, state — **"Read and sign"** (outline button) or green chip
  `check` "Signed".
- **Read and sign** opens the paper page: the paper shown in the page (PDF pages rendered as images by the
  server, scrolling vertically) with a link "Open the paper" for the PDF itself. If the server cannot turn
  PDF pages into images without new software, the page instead shows a large **"Open the paper"** button (the
  PDF opens in a new tab) and the tick stays disabled until it has been pressed. Below it:
  - tick: "I have read **{paper name}** and I agree to it."
  - signature pad: white box 100% × 180px, dashed line, hint "Sign here with your finger"; **"Clear"** ghost.
  - full name field prefilled, editable ("Your name as you sign it").
  - primary **"Sign"** — enabled when the tick is on, the pad has ink, the name is not empty.
- After signing: back to the list; row shows "Signed · {14:02, 27 Nov}". A signed paper cannot be re-signed by
  the person; HR can ask for it again (Send back).
- First signature is remembered for this visit: the next paper offers "Use the signature I just drew" (still
  requires the tick and the press).
- Section is done when every paper is signed.

### 7.7 Your first day

- First-day card: `sun` "**{Monday 14 December}, {8:00 am}**"; `mapPin` place; "Ask for **{name}**"; "Bring:
  {what to bring}". Lines with no value are omitted; if nothing at all is set: "Your manager will send you the
  time and place before you start."
- Buddy card (if Hiring has a buddy): avatar, "**{name}** is your buddy", their job title.
- Laptop question (only when Hiring's "Before they join" list has an open laptop item for this offer): the same
  questions as the existing laptop page, answered here; answering closes that item in Hiring.
- Footer primary **"Got it"** → marks the section done.

### 7.8 Sent and Day one

- **Sent:** hello card with green chip `check` "Sent to HR"; `h2` "All done, {first name}. See you on
  {Monday 14 December}."; "HR will check what you sent. If anything needs fixing you will get a message and it
  will show here." Then the first-day card and buddy card. If the bank is "later": an amber row **"Bank account
  still to add"** — "Add it before {date} to be in your first pay" → opens the bank section (still editable
  after sending). Every other section is read-only, sensitive values masked.
- **Sent back:** the hub returns (§7.4) with only the sent-back sections editable; the footer button reads
  **"Send again"**.
- **Day one** (after HR has added the person): `h2` "Welcome aboard, {first name}"; first-day card; buddy;
  and one line on signing in — "From today you use My Payobook. {HR contact name} will give you your sign-in."
  Nothing is editable.

### 7.9 Language

A two- or three-option segmented control ("English · Tiếng Việt · Bahasa Indonesia", only languages installed
on the site). Default = the language the person applied in (Hiring), else the site default. The choice is
remembered on the joining and used for emails and reminders.

### 7.10 Messages to the person

Sent in the person's language, from the company's hiring sender. When the site cannot send email or the person
has no email, nothing is sent and the board shows what HR must pass on (§8.4).

| Key | When | Subject | Body (essence) |
|---|---|---|---|
| joining link | offer signed / invited / "Send again" | "Welcome to {company}. A few details before you start" | Greeting; "Before {first day} we need a few details from you. It takes about 10 minutes on your phone."; button **"Fill in my details"**; "You will be asked for a 6-digit code. We send it when you open the link." |
| code | the person opens the link or asks for a new code | "{123456} is your code" | "Your code for {company} is **123 456**. It works for 10 minutes. If you did not ask for it, ignore this message." |
| reminder | every 3 days while not sent (max 4) | "{first name}, your details for {company}" | What is still needed (section names), the button, the first day. |
| sent back | HR sends something back | "One thing to fix before you start" | The item names and HR's notes, the button. |

---

## 8. The Joining board (back office)

One OWL component, mounted as the **"Joining"** tab in the Hiring hub (after Offers in reading order; icon
`userPlus`) and in the People hub (immediately before "Joiners"). Also a ⌘K row "Joining — people who have
signed and not yet started".

Built on the product's quiet-board pattern, same structure as People › Joiners (do not invent a new board
skeleton):

### 8.1 Header

Title is the hub's own. Right side: outline **"Invite someone"** (`userPlus`, §8.6); ghost **"What a joiner
is asked"** (opens Add employee's existing paper settings) and **"Papers to sign"** (§8.7) for people who may
manage.

### 8.2 Glance strip (five figures, QuietGlance)

| Figure | Label | Tone | Click |
|---|---|---|---|
| people in steps 1–3 | "joining in the next 30 days" (counts first day ≤ today+30) | — | clears step filter |
| step 3 count | "waiting for your check" | indigo (plain) | step 3 |
| at-risk count | "at risk of missing first pay" | rose | filter At risk |
| link-not-passed count | "link to pass on" | amber | filter To pass on |
| started-this-week | "started filling in this week" | green | step 2 |

### 8.3 Steps strip (QuietSteps) and cards

Four steps: **01 Invited** ("Offer signed. The link has gone out."), **02 Filling in** ("They have started.
Reminders run by themselves."), **03 Ready for you to check** ("Everything sent. Nothing is in the employee
record yet."), **04 Ready for day one** ("Checked and added as an employee."). Picking a step filters the
grid; default on arrival = step 3 if it has people, else all.

Filter panel (filter kit): step, Country of work, team, first day (this week / next 2 weeks / this month),
flags (At risk, To pass on, Sent back, Bank still to come), where from (Hiring / Invited). Search by name, job,
team. Sort: first day soonest (default), most complete, least complete, newest.

**Card** (grid, same proportions as the Joiners cards):

1. Avatar (initials; teal tint), **name**, "job · Country of work".
2. "Starts **Mon 14 Dec** · 17 days" (rose when ≤ 3 days and not in step 4).
3. Progress bar + "%" (share of required sections done; step 4 = 100%).
4. One line of chips, most important first, max 3:
   - rose `alertTriangle` **"At risk: {what is missing}, {n} days left"** — not sent and first day ≤ 7 days, or
     a first-pay item still missing ≤ 7 days.
   - amber `send` **"Link to pass on"** — no email could be sent and the link has never been copied.
   - amber `clock` **"Not opened yet · reminded {2 days ago}"**.
   - indigo `eye` **"Waiting for your check"**.
   - amber `arrowLeft` **"Sent back · {n}"**.
   - amber `landmark` **"Bank account still to come"**.
   - green `check` **"Employee record made"**.
5. Foot line, muted: "Before they join {2 of 4}" (Hiring's list, when the joining came from Hiring).

Empty states: nobody at all — icon `userPlus`, "**Nobody is joining yet**", "People appear here the moment
their offer is signed in Hiring. You can also invite someone hired another way.", button "Invite someone".
Step with nobody — "Nobody here".

### 8.4 The drawer (click a card)

Right slide-over, 560px, own scrim (the product's per-board drawer pattern). Sections top to bottom:

**Head:** avatar, name, "job · Country of work · starts Mon 14 Dec", step chip; close `x`.

**Link strip** (soft panel): state sentence + buttons, for people who may manage:
- email sent: "Link emailed to d•••@gmail.com on 27 Nov." — **"Send again"**, **"Copy link"**.
- cannot email: "This site cannot send email. Pass the link and a code to {first name} yourself." —
  **"Copy link"**, **"Show a code"**.
- **Show a code** reveals, inline in the strip, a fresh 6-digit code in large tabular digits ("**482 915** ·
  works for 48 hours, once") with **"Copy"**; it is shown once and never again (pressing again makes a new one
  and cancels the old). Sub-line: "Send the link and the code separately."
- Activity lines under it: "Opened 27 Nov, 14:02 · last seen today 09:15", "Reminded 2 times".

**What they sent** — one row per catalogue item (not per section; `Your first day` has no row), each:
- 32px icon tile, item label (catalogue label), source chip where it applies (`From Hiring` on personal
  details partly held; `Read from Hiring's paper` on papers Hiring already had).
- The values as a two-column list (label · value). Sensitive values masked with an `eye` button that reveals
  for 30 seconds (only for people who may manage; each reveal is logged on the joining's history).
- Files as thumbnails / file chips that open in the viewer.
- State + actions on the right:
  - not sent yet → grey chip "Not sent yet".
  - "remind me later" / "I do not have one yet" → amber chip "They will add it later" / "They do not have one
    yet".
  - sent, awaiting check (step 3) → **"Accept"** (outline, `check`) and **"Send back"** (ghost). Send back opens
    an inline note field under the row — "What should {first name} fix?" (required, 200 chars) + **"Send
    back"** / "Cancel".
  - accepted → green chip `check` "Accepted" + ghost "Undo" (until added).
  - sent back → amber chip "Sent back to fix" + the note.
  - added → green chip "In the record".
- Signed papers: row per paper with "Signed 27 Nov, 14:02" and a link to the signed copy (paper + signing
  page).

**Foot** (sticky):
- steps 1–2: **"Send a reminder now"** (outline; when email is off it copies a ready message instead and says
  "Message copied. Paste it into WhatsApp or a text."), ghost "Copy link".
- step 3: outline **"Accept everything"**; primary `userPlus` **"Add as employee"** — enabled when every sent
  item is accepted and no item is awaiting a decision (items marked "later"/"do not have one" do not block).
  Under it: "Accepting saves nothing yet. The details go into the employee record only when you press Add in
  the next screen."
  If any item was sent back: the primary is replaced by a note "Waiting for {first name} to fix {n} thing(s)."
- step 4: note "{name} is an employee." + outline **"Open in Joiners"**.
- Always, in a `…` menu: **"First-day details"** (§8.5), **"Change the first day"**, **"They are not joining"**
  (asks for a reason; closes the link; for a Hiring offer it runs Hiring's own "Did not join").

**Who sees what:**
- People who may add employees (the Add employee gate) see everything and can act.
- Recruiters, talent leads, the hiring manager of that role, lifecycle team: see the board, cards, progress,
  chips and the link strip (Send again / Copy link / Show a code); in "What they sent" they see **item names
  and states only — no values, no files**.
- Everyone else: the tab is hidden.
- A refused reader gets the product's lock card, never an error.

### 8.5 First-day details (small form in the drawer)

Time (text, e.g. "8:00 am"), place, ask for (person chooser or text), what to bring, a note from the manager
(the manager or HR types it; shown on the welcome screen in quotes). Company-wide defaults for place and what
to bring live in the board's settings and pre-fill each joining.

### 8.6 Invite someone (drawer form)

Fields: full name*; first day*; Country of work* (the Add employee country list); job title*; team (optional);
manager (optional); personal email; mobile; language. At least one of email / mobile is required ("So the link
can reach them."). Primary **"Invite"**. Result line: "Link emailed to …" or "Copy the link and show a code to
pass on." The person lands in step 1.

### 8.7 Papers to sign (settings drawer)

List of the company's papers: name, Country of work (blank = every country), the PDF, on/off, order. "Add a
paper" uploads a PDF (max 5 MB). No papers → the phone has no "Sign your papers" section. Removing a paper does
not remove copies already signed.

---

## 9. Add employee, after

Nothing about the screen's layout changes. Three additions:

### 9.1 Arriving from the board ("Add as employee")

- The studio opens on **step 7 Check and add** with steps 1–6 marked done where their required answers are
  present; any step missing a required answer (always possible for "Invite someone" people: team, job, wage)
  is marked "needed" and the studio opens on the first such step instead.
- Steps 1–3 are brought across from Hiring exactly as "From Hiring › Bring across" does today.
- Step 5 rows that the person sent and HR accepted show the new third way, selected by default:
  **"From {first name}"** (teal chip) with the sub-line "Sent by {first name} on 27 Nov · accepted by {you}".
  The values show read-only (sensitive ones masked as the approver view already does). HR can switch the row to
  "I have it" (then types their own) or "Ask {first name}" (the existing after-hire ask).
- Rows the person marked "later" / "do not have one" default to **"Ask {first name}"** (existing behaviour: the
  after-hire welcome link asks for it).
- The left rail sub-lines read as in the prototype: "From Hiring", "From the signed offer", "Team defaults",
  "From {first name}, checked by you", "Checklist is ready".
- The right panel "Who does what" counts items already sent by the person as done.

### 9.2 The "From Hiring" tile on step 1

Each waiting offer row gains a chip: teal "Details 100% in · checked" / amber "Details 60% in" / grey "Link
not opened". "Bring across" on a row whose details are checked behaves as §9.1.

### 9.3 After Add

On success the done card adds one line: "{first name}'s details, papers and signed papers came across from the
Joining board." The joining moves to **Ready for day one**. Second-person approval of the hire and of the bank
account run exactly as today; if the hire waits for approval the card stays in step 3 with chip "Waiting for
approval of the hire" and the joining moves to step 4 when the approval applies.

---

## 10. States and edge cases

| Case | Behaviour |
|---|---|
| Offer signed with `quiet` (data replay) | Nothing is created or sent. |
| Internal candidate (staff move) | No joining is created. |
| The switch "Send the joining link when an offer is signed" is off | No joining is created automatically; HR can still "Invite someone" from a signed offer row (the invite form pre-fills from the offer). |
| No email on the site or the person | Joining is created; card shows "Link to pass on"; HR is notified in the product. |
| First day changed in Hiring or from the drawer | Joining's first day follows; reminders and "at risk" recalculate. |
| Did not join (Hiring) / "They are not joining" | Joining closed; link shows "not active"; values and files erased 30 days later. |
| Person edits after HR accepted an item | Not possible; accepted items are read-only on the phone. HR must "Undo" or "Send back". |
| Bank marked later, person adds it after sending | The card returns to step 3 with that one row awaiting check (if not yet added), or — if already added as an employee — the bank section closes and the phone says "Add your bank account in My Payobook". |
| HR presses "Add as employee" then leaves the studio | Nothing changes; the card stays in step 3. |
| Hire withdrawn or rejected in approval | Card stays in step 3; chip "The hire was sent back"; "Add as employee" available again. |
| Two HR people act at once | The second sees the current state with a toast "Updated by {name} just now." |
| Link opened on a new device | Code screen again. |
| 5 wrong codes | Locked 15 minutes; HR sees "Locked after wrong codes" in the link strip. |
| Country of work changed after the person started | Sections recalculate; answers for items that no longer exist are kept hidden (not deleted) until the joining closes; new items show as not started; if already sent, the card returns to Filling in with chip "Country of work changed". |
| Person already has a waiting joining for the same offer | Never two; the existing one is reused. |

## 11. Where the prototype differs from this specification

| Prototype | Build |
|---|---|
| Board drawn as four columns | Quiet-board pattern: steps strip + filterable card grid + slide-over drawer (§8). Same four steps, same card content. |
| "We read this from your card" (card reading) | **Not in this build.** The person takes a photo and types the number. |
| New Zealand tax fields | Illustrative only. Countries follow the catalogue (§5). |
| "Marital status", "Uniform size", "Laptop" free fields | Not built. Tax status comes from the catalogue; the laptop question appears only when Hiring asked it. |
| "Family and emergency contact" | Section is "Emergency contact". |
| No "Your papers" section | Added (§5 row 6). |
| "Welcome checklist — started on signing" | Not possible before the employee exists. Hiring's "Before they join" list is the pre-day-one list; the welcome checklist still starts at Add. Step 6 sub-line stays "Checklist is ready". |
| Review panel sits under the board | It is the card's slide-over drawer. |
| "Day 7, 30, 60, 90" stage in the plan | Later (O6). |
| "Fill the rest for me (demo shortcut)", "Start Dewi again" | Prototype helpers. Not built. |
| Bahasa/English chips on welcome | A working language control (§7.9). |

## 12. Acceptance — what "done" looks like to the owner

1. Recording a signed copy in Hiring puts the person on Hiring › Joining and People › Joining within the same
   click, with either "Link emailed" or "Link to pass on".
2. On a phone, the link + code opens a page in the company's colours; the person can finish in about ten
   minutes, leave halfway and return, and send.
3. The board shows them move from Invited to Filling in to Ready for you to check without anyone refreshing
   data by hand (a reload of the tab is enough).
4. HR accepts or sends back each item; a sent-back item reopens on the phone with HR's note.
5. "Add as employee" opens Add employee with nothing to type for a person who came from Hiring.
6. After Add: the employee has the typed details, the papers, the signed papers; the bank account waits for a
   second person; the card says Ready for day one.
7. A recruiter can follow progress but cannot see a bank account or identity number.
8. Everything reads correctly in English, Vietnamese and Indonesian, and the word "Odoo" appears nowhere.
