# PayAI does it — design spec (owner-approved 2026-10-12)

Interactive design page the owner reviewed: https://claude.ai/artifact/3t8BLmEm28WzzQehS5BsKa
(file copy: `payai-does-it.html` beside this file). Engineering detail, verified plumbing and the phase plan
live in `docs/handovers/payai/PAYAI_PROGRAM.md`; gotchas in `docs/handovers/payai/PAYAI_LEDGER.md`.

## What it is
PayAI carries out the things a person otherwise does by clicking through screens — run a pay run, send it for
approval, change a pay value, approve as the seat holder, open any screen — from a typed or spoken sentence.

## The model, in one paragraph
The AI never touches records. It picks a **named Action** from a server-owned catalogue and extracts slot
**text**; the server **resolves** every slot against what the asking user may see, runs the Action's **gate**
(Access-home screen visibility AND the method-level right), builds a **Plan card** from the same preview methods
the screen uses, and waits for the confirmation the Action's **tier** demands. Execution calls the exact methods
the screen calls, as the user, never sudo. Every request leaves a `payai.task` row (audit) and the card offers the
Action's compensating **undo** for ten minutes.

## Tiers (colours)
| Tier | What | Confirm | Undo |
|---|---|---|---|
| Green · Look | open a screen, run status, counts, download Excel | none | — |
| Amber · Prepare | run payroll (draft), send for approval, change a pay value, send payslips, prepare a filing | plan card + one tap; spoken "go ahead" if the company switch allows | 10 min: delete draft run / withdraw / revert |
| Red · Decide | approve, send back, reject (seat holder only) | plan card + typed word; never voice | workflow only |
| Blocked | pay money, bank files, delete runs/payslips, clean-and-run, access changes | refused + the door to the screen | — |

## Plan card anatomy
Title + tier line · one row per slot with its origin chip (**you said / you chose / assumed / default**) and an edit
pencil · a note line with the real counts (people covered, existing run, approvals needed) · actions
(**Do it** primary · **Open in the screen instead** outline · Cancel ghost) · after Do it: progress bar → result
tiles → next-step buttons → undo banner with countdown → audit line.

## Owner decisions (2026-10-12, do not re-ask)
Phased Fable↔Opus; Green+Amber+Red at launch; same rights as the screen with the **no back door** rail; in-chat
execution + pre-filled screen escape hatch; English first, Vietnamese last; Amber = one tap (+ voice go-ahead
behind a company switch), Red = typed word; first release = run payroll, send for approval, open any screen, run
status, download Excel, change a pay value, approve/send back/reject, send payslips, government filing; security
fix (P0) first on every database.

## Phases
P0 security hardening (done by Fable) · P1 foundation + Green · P2 Amber · P3 Red · P4 Vietnamese + close-out.
