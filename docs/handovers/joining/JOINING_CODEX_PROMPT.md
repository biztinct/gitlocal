# Prompt to paste into the coding session

```
You are building a feature called the JOINING PORTAL for Payobook (an HR + payroll product built as custom
Odoo 19 modules). The design is finished and approved by the owner. Your job is to build it exactly as
designed, test it, release it, and report back. Ask me only if something in the design pack is contradictory
or impossible; otherwise decide, note the decision in your report, and keep going.

REPOSITORY
- Main checkout: /Users/adity/Documents/GitHub/gitlocal (branch 19.1). DO NOT build there: it is 182 commits
  behind origin/19.1 and has unrelated uncommitted files.
- Create a fresh worktree from origin/19.1 on a new branch `joining` and do all work there:
    cd /Users/adity/Documents/GitHub/gitlocal && git fetch origin 19.1
    git worktree add ../gitlocal-worktrees/joining -b joining origin/19.1
- If tools/release.sh is missing in the worktree: git cherry-pick 840036012
- Copy the design pack into the worktree and commit it first ("JOINING docs: design pack"):
    /Users/adity/Documents/GitHub/gitlocal/docs/handovers/joining/   (all files)
    /Users/adity/Documents/GitHub/gitlocal/docs/design/joining-portal-poc.html

READ THESE FIRST, IN THIS ORDER (they are the whole brief)
1. docs/handovers/joining/JOINING_LEDGER.md          rules that bind everything you do
2. docs/handovers/joining/JOINING_DESIGN.md          every screen, every word, every state (binding)
3. docs/design/joining-portal-poc.html               clickable prototype: open it in a browser and click
                                                     through all five tabs; it defines look, tone and wording
4. docs/handovers/joining/JOINING_FACTS.md           verified code facts with file:line. Do not re-derive
5. docs/handovers/joining/JOINING_BUILD_HANDOVER.md  scope, non-goals, architecture, phases P1-P4,
                                                     70 numbered tests, browser walks, release, report format
Then skim docs/handovers/newhire/NEWHIRE_LEDGER.md, docs/handovers/recruit/RECRUIT_LEDGER.md and CLAUDE.md.

WHAT YOU ARE BUILDING (one paragraph)
When a job offer is recorded as signed in Hiring, the new person gets a link. They open it on their phone with
a 6-digit one-time code (no password), fill in their own details (personal, identity card, bank account, tax
and social insurance numbers, emergency contact, papers), sign the company's papers with a finger, and send.
HR follows everyone on a new "Joining" board that is a tab in both the Hiring hub and the People hub, accepts
or sends back each item, and presses "Add as employee", which opens the existing Add employee screen already
filled in. Nothing the person sends touches the employee record except through that existing screen.

HARD RULES (full list in the ledger and handover)
- New module pb_joining. Extend pb_hiring and pb_new_hire by inheritance; edit pb_new_hire only to add a
  missing extension seam, and list each such edit in your report.
- One catalogue: the phone's fields come from Add employee's step-5 catalogue and pb.bank.format. Never define
  a second list of fields or validation rules.
- The word "Odoo" must never appear in anything a user can see (screens, emails, public pages, manifest name
  and summary, translations). Technical identifiers are untouched.
- Match the existing design system: indigo #5A4BB0, the --pbim-* tokens and .pbim-* classes, Lucide icons
  through ic(), the quiet-board pattern for the board, the Add employee studio's look. No emoji, no gradients,
  one solid primary button per screen. Quality bar from the owner: "exceptional premium, extreme WOW, a novice
  can work without training".
- English, Vietnamese (vi_VN) and Indonesian (id_ID) from the start.
- Security of the one-time code and the public pages is specified in handover sections 2 and 3. Implement it
  exactly and unit-test every branch.
- No new server packages or standard-module dependencies. Never touch the abm database. No credentials or real
  personal data in the repo.

HOW TO WORK
- Phases P1 -> P4 in order (handover section 5). At the end of each phase: run the numbered tests for that
  phase plus the full suites of every module you touched (baseline failures only), do the browser walks for
  that phase with the console open, commit ("JOINING P1: ...") with explicit file staging, push.
- Record a test baseline for pb_hiring, pb_new_hire and pb_onboarding BEFORE changing anything.
- A screen is not finished until you have used it in a real browser. Save screenshots under
  docs/handovers/joining/shots/.
- Append every new gotcha to JOINING_LEDGER.md section 4.

RELEASE (the owner decided you also release)
Follow handover section 8 exactly: read /opt/deploy-notes.md on the server first, use tools/release.sh (tier
risky, +pb_joining to install) for all five databases (payobook, payobook_template, p0clone, rize, sudima),
verify, write the NOTE line, then do the live proof on payobook only with a DEMO-prefixed person. Create
nothing on rize or sudima. If the release script does not return OK, stop and report; do not improvise. If you
need a live sign-in, ask me to sign in for you; never store a password.

WHEN YOU FINISH
Write docs/handovers/joining/JOINING_REPORT.md in the format of handover section 9 (what was built, test
counts before/after, every deviation from the design and why, walk results with screenshot paths, release
result, new ledger entries, open questions for the owner in plain non-technical English). Then give me a
short plain-English summary: what now works, what I should click to see it, and anything you need me to decide.
```
