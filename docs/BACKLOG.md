# Backlog

Ideas and requests waiting to be built. Nothing here is started until the owner
picks an item and asks for it. Add new items at the bottom, keep the numbering.

Status values: `Open` (not started), `In progress`, `Done`, `Dropped`.

---

## 1. Improve the Payslip Studio

**Status:** Open
**Raised:** 2026-09-11

Make the Payslip Studio better. Scope not yet defined — the owner will say what
"better" means (look, speed, editing, preview, templates) when this item is
picked up.

**Open questions for the owner**
- Which part feels weakest today: the design of the payslip, the editing
  experience, or the preview/print result?
- Is this about the payslip template designer, or the payslip screen itself?

---

## 2. Load and remove demo data for every tenant

**Status:** Open
**Raised:** 2026-09-11

Every tenant should be able to fill itself with demo data on demand, using the
same script that was already built to create the demo world on
rize.payobook.com. The same feature must also be able to delete that demo data
again, cleanly, leaving the tenant's real data untouched.

**What the owner asked for**
- A button or option that creates the demo data in a tenant.
- The same place lets you delete the demo data when it is no longer wanted.
- It is part of creating a tenant, and every tenant has it — not a one-off
  script run by hand.

**Open questions for the owner**
- Should a brand-new tenant get demo data automatically, or only when someone
  presses the button?
- Should deleting demo data be allowed at any time, or blocked once real pay
  runs exist?

---

## 3. Fill the rest of the period fields automatically

**Status:** Open
**Raised:** 2026-09-11

Only the month fills itself today. The other period values a rule may need —
days in the month, the year, and the wider set beside them — still have to be
typed in by hand.

**What the owner asked for**
- The whole period family fills itself the way the month already does.

**Open questions for the owner**
- Which period values matter most: days in the month, working days, the year,
  the start and end dates, or all of them?
- Should the filled values be visible and editable on screen, or read-only?

---

## 4. A screen to create your own statutory pack

**Status:** Open
**Raised:** 2026-09-11

Statutory packs ship with the product. You can change the values inside one
configuration, and roll a shipped pack across many configurations, but there is
no way to author a new pack of your own.

**What the owner asked for**
- A screen that creates a statutory pack from scratch, not just edits a
  shipped one.

**Open questions for the owner**
- Can anyone author a pack, or only an administrator?
- Should an authored pack be shareable across tenants, or stay inside the one
  it was built in?

---

## 5. A pop-up on any field that explains what it is

**Status:** Open
**Raised:** 2026-09-18

Any field on any screen can show a small pop-up that explains it properly, so
nobody has to guess what to type or ask someone.

**What the owner asked for**
- Click (or hover) a field and a pop-up opens on the spot.
- Short line first: what this field is, in plain words.
- Then a fuller explanation for people who want the detail.
- At least one worked example with real-looking values.
- Links across to the other fields it is tied to — for example, if this is a
  minimum and there is a matching maximum somewhere else, the pop-up says so and
  takes you there.

**Open questions for the owner**
- Should this cover every field everywhere, or start with the screens people
  get stuck on (pay setup, statutory, mapping)?
- Who writes the text — do we ship it, or can an administrator edit it per
  tenant?
- Vietnamese as well as English from day one?

---
