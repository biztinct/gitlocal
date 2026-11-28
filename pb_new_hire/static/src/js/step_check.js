/** @odoo-module **/
/**
 * Step 7 — Check and add (NEWHIRE P1). One last look, every problem in amber
 * with its fix, what pressing the button really does (from the approval
 * engine's own route), and the one button. After Send: the done card —
 * waiting ("Withdraw and change", D7) or added ("Open the record").
 *
 * P2: rows for steps 4 and 6; "When you press the button" reads the first
 * things of step 6's own timeline (one source, so it cannot drift); the done
 * card shows the welcome legs — one green line when all went well, an amber
 * row for each that did not — and "See new joiners".
 */
import { printSignInSlips } from "@biz_access/js/access_board";
import { Component, useState, useEffect } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { icon, fmtDay, money, rich, weekNameOf, ownMissingOf, docItemsOf, docSummaryChoiceOf, docGapsOf, docTallyOf,
         docAskedOf, errorText, copyText } from "./studio_util";

export class StepCheck extends Component {
    static template = "pb_new_hire.StepCheck";
    static props = { api: Object };

    setup() {
        this.icon = icon;
        this.nh = useState(this.props.api.nh);
        // P3b: the done card of an ADDED person reads the real asks (and
        // whether the welcome link can be copied here) once
        this.card = useState({ data: null, busy: false, link: "", hint: "", slip: null, slipBusy: false });
        useEffect((empId, applied) => {
            if (applied && empId) {
                this.loadCard(empId);
            } else {
                this.card.data = null;
                this.card.link = "";
            }
        }, () => [this.result && this.result.employee_id, Boolean(this.result && this.result.applied)]);
    }

    get api() { return this.props.api; }
    get d() { return this.nh.draft; }
    get dec() { return this.nh.decides; }
    get first() { return this.api.first; }
    get name() { return String(this.d.name || "").trim(); }
    get approval() { return (this.nh.data && this.nh.data.approval) || { needs: true }; }
    get result() { return this.nh.result; }

    // ------------------------------------------------------------ the list
    get rows() {
        const api = this.api;
        const d = this.d;
        const out = [];
        out.push(api.status("who").state === "done"
            ? { key: "who", cls: "", icon: "check", b: this.name, s: _t("First day %s", fmtDay(d.date_start, true)), go: "who", field: "name" }
            : { key: "who", cls: "is-bad", icon: "alert", b: _t("Name and first day are missing"), s: _t("Step 1"), go: "who", field: d.name ? "date_start" : "name" });
        if (api.status("role").state !== "warn") {
            const bits = [api.countryName,
                d.parent_name ? _t("reports to %s", d.parent_name) : _t("no manager yet"),
                this.siteName || _t("no site")];
            out.push({ key: "role", cls: "", icon: "check", b: _t("%(job)s, %(team)s", { job: api.jobName, team: api.teamName }),
                       s: bits.join(" · "), go: "role", field: "department_id" });
        } else {
            out.push({ key: "role", cls: "is-bad", icon: "alert", b: _t("Team, job or country is missing"), s: _t("Step 2"), go: "role", field: "department_id" });
        }
        if (api.status("pay").state !== "warn") {
            const answer = this.nh.payAnswer;
            const head = answer?.head;
            const annual = head && !head.is_wage && head.period === "year";
            const amount = head && !head.is_wage ? d.usual?.[head.code] ?? head.usual : d.wage;
            const wage = amount > 0 ? money(amount, api.currency) : _t("Pay from the pay scale");
            const kind = d.contract_kind === "fixed" ? _t("fixed term to %s", fmtDay(d.date_end)) : _t("permanent");
            const trial = this.trialEnds ? _t("trial to %s", fmtDay(this.trialEnds)) : _t("no trial period");
            const scheme = this.dec?.scheme ? _t("Paid by %s", this.dec.scheme.name) : _t("No pay scheme yet");
            const title = annual ? _t("%(wage)s a year, %(kind)s", { wage, kind })
                : amount > 0 ? _t("%(wage)s a month, %(kind)s", { wage, kind }) : _t("%(wage)s, %(kind)s", { wage, kind });
            const terms = [...(answer?.asks || []), ...(answer?.sections || []).flatMap(section => section.lines)];
            const changes = terms.filter(row => row.kind === "set" && Object.hasOwn(d.usual, row.code)).map(row => {
                const value = d.usual[row.code];
                return row.name + " " + (row.control === "money" ? money(value, api.currency) : value);
            });
            out.push({ key: "pay", cls: "", icon: "check", b: title, s: [scheme, trial, ...changes].join(" · "),
                       go: "pay", field: "wage" });
        } else {
            out.push({ key: "pay", cls: "is-bad", icon: "alert", b: _t("The wage is missing"), s: _t("Step 3"), go: "pay", field: "wage" });
        }
        out.push(this.schedRow);
        out.push(this.docsRow);
        out.push(this.welcomeRow);
        return out;
    }
    get schedRow() {
        const d = this.d;
        const week = weekNameOf(this.nh) || _t("The company's usual working hours");
        const late = this.nh.sched && this.nh.sched.late_groups
            ? (d.late_group === "manager" ? _t("late rule: Manager") : _t("late rule: Worker")) : "";
        const code = String(d.clock_code || "").trim();
        const clock = d.clock_on ? (code ? _t("clock number %s", code) : _t("clocks in, number to add later")) : _t("no clocking");
        return { key: "sched", cls: "", icon: "check", b: week, s: [clock, late].filter(Boolean).join(" · "),
                 go: "sched", field: "week_id" };
    }
    get welcomeRow() {
        const d = this.d;
        const w = this.nh.welcome;
        const modes = { email: _t("Sign-in by email invitation"), code: _t("Sign-in by employee number"), none: _t("No sign-in yet") };
        const mode = d.login_mode || (w && w.login && w.login.chosen) || "none";
        const bits = [];
        const caseOn = d.open_case !== false && w && w.case && w.case.available;
        if (caseOn) {
            const n = Array.isArray(d.equipment) ? d.equipment.length : null;
            bits.push(n === null ? _t("laptop request") : n === 1 ? _t("1 equipment request") : _t("%s equipment requests", n));
            bits.push(d.buddy_id ? _t("buddy %s", d.buddy_name) : _t("manager chooses the buddy"));
        } else {
            bits.push(_t("no joining checklist"));
        }
        if (w && w.letter && w.letter.available && d.letter !== false) {
            bits.push(_t("contract letter prepared"));
        }
        return { key: "welcome", cls: "", icon: "check", b: modes[mode] || modes.none, s: bits.join(" · "),
                 go: "welcome", field: false };
    }
    /** P3a: step 5 in one line — who gives what. */
    get docsRow() {
        const items = docItemsOf(this.nh);
        if (!items.length) {
            return { key: "docs", cls: "is-soon", icon: "hourglass", b: _t("Details and documents"),
                     s: _t("Choose the country of work first."), go: "docs", field: false };
        }
        const t = docTallyOf(this.nh);
        const pick = (c) => items.filter((i) => docSummaryChoiceOf(this.nh, i) === c).map((i) => i.label);
        const bits = [];
        if (t.ask) {
            bits.push(_t("Asked: %s", docAskedOf(this.nh).map((a) => a.label).join(", ")));
        }
        if (t.have) {
            // a number-only card row: the number is with you
            const mine = items.filter((i) => ["have", "number"].includes(docSummaryChoiceOf(this.nh, i)))
                .map((i) => (docSummaryChoiceOf(this.nh, i) === "number" ? i.fields[0].label : i.label));
            bits.push(_t("With you: %s", mine.join(", ")));
        }
        if (t.later) {
            bits.push(_t("Later: %s", pick("later").join(", ")));
        }
        return { key: "docs", cls: "", icon: "check",
                 b: _t("%(ask)s for %(first)s, %(have)s with you", { ask: t.ask, first: this.first, have: t.have }),
                 s: bits.join(" · ") || _t("Nothing asked for"), go: "docs", field: false };
    }
    get siteName() {
        const s = ((this.nh.data && this.nh.data.sites) || []).find((x) => x.id === this.d.work_location_id);
        return s ? s.name : "";
    }
    get trialEnds() {
        const t = this.dec && this.dec.trial;
        return t && this.d.trial_on ? t.ends : "";
    }

    /** Amber rows: things that may be wrong. None of them blocks sending. */
    get warnings() {
        const out = [];
        if (this.dec && this.dec.problem) {
            out.push({ key: "scheme", b: this.dec.problem, s: this.dec.fix || "", go: "role",
                       field: this.dec.scheme && this.dec.scheme.match ? "department_id" : "payroll_country" });
        }
        const same = (this.nh.dup && this.nh.dup.same_name) || [];
        if (same.length) {
            out.push({ key: "dup", b: _t("%s is already an employee", same[0].name),
                       s: _t("Carry on only if this is a different person."), go: "who", field: "name" });
        }
        if (this.nh.dup && this.nh.dup.email_taken) {
            out.push({ key: "email", b: _t("Another employee already uses this work email"),
                       s: _t("Check it, or leave the work email empty."), go: "who", field: "work_email" });
        }
        const clock = this.nh.clockCheck;
        if (clock && clock.ok === false) {
            out.push({ key: "clock", b: clock.message, s: _t("The hire is still added; only the clock number would be left out."),
                       go: "sched", field: "clock_code" });
        }
        for (const item of docGapsOf(this.nh)) {
            out.push({ key: `doc-${item.key}`, b: _t("%s is not finished", item.label),
                       s: _t("You chose I have it, so type it or attach the file, or choose another answer."),
                       go: "docs", field: `doc-${item.key}` });
        }
        for (const item of docItemsOf(this.nh)) {
            if (item.need === "first_pay" && docSummaryChoiceOf(this.nh, item) === "later") {
                out.push({ key: `later-${item.key}`, b: _t("%s is needed before the first pay", item.label),
                           s: _t("Nobody is asked for it. Add it on the record before the first pay run."),
                           go: "docs", field: `doc-${item.key}` });
            }
        }
        for (const f of ownMissingOf(this.nh)) {
            out.push({ key: `own-${f.name}`, b: _t("%s is needed", f.label),
                       s: _t("It is required on every employee record, so the hire cannot be sent without it."),
                       go: "welcome", field: `own-${f.name}` });
        }
        return out;
    }
    change(row) { this.api.go(row.go, row.field); }

    // ------------------------------------------------------------ what happens
    get then() {
        const out = [];
        const cur = this.api.currency;
        const code = cur ? cur.name : "";
        const scheme = this.dec && this.dec.scheme ? this.dec.scheme.name : "";
        if (this.approval.needs) {
            out.push(this.approval.with_whom
                ? rich(_t("%(who)s gets the hire to approve. Nothing is created until they agree."), { who: this.approval.with_whom })
                : rich(_t("A second person gets the hire to approve. Nothing is created until they agree.")));
            out.push(scheme
                ? rich(_t("On approval, the employee record and a running contract are created, in %(code)s, on %(scheme)s."), { code, scheme })
                : rich(_t("On approval, the employee record and a running contract are created, in %(code)s."), { code }));
        } else {
            out.push(scheme
                ? rich(_t("%(name)s is added straight away, with a running contract in %(code)s on %(scheme)s."), { name: this.name || this.first, code, scheme })
                : rich(_t("%(name)s is added straight away, with a running contract in %(code)s."), { name: this.name || this.first, code }));
        }
        if (this.dec && this.dec.pay_line) {
            // P8 A.4: who will pay them, and how to make it the team's own
            out.push(rich(this.dec.pay_line));
        }
        if (this.trialEnds) {
            out.push(rich(_t("The trial period is set to end on %(day)s."), { day: fmtDay(this.trialEnds, true) }));
        }
        for (const e of this.head) {
            out.push(rich(_t("%(when)s: %(what)s (%(who)s)."),
                          { when: e.past ? _t("Straight away") : fmtDay(e.when) }, { what: e.title, who: e.who }));
        }
        const bank = docItemsOf(this.nh).find((i) => i.key === "bank");
        const bankChoice = bank ? docSummaryChoiceOf(this.nh, bank) : "";
        if (bankChoice === "have") {
            out.push(rich(_t("The bank account goes to a second person for approval, as every bank change does.")));
        } else if (bankChoice === "ask") {
            out.push(rich(_t("%(first)s is asked for the bank account on My Payobook, and a second person approves it."), { first: this.first }));
        } else {
            out.push(rich(_t("Bank account: add it from the employee's side panel later.")));
        }
        const asks = docAskedOf(this.nh).length;
        if (asks) {
            out.push(this.welcomeLine(asks));
        }
        return out;
    }
    /** P3b: what really happens to the asks — one welcome message, or why not. */
    welcomeLine(n) {
        const d = this.d;
        const personal = String(d.personal || "").trim();
        const address = personal.includes("@") ? personal : String(d.work_email || "").trim();
        const w = this.nh.welcome;
        const mode = d.login_mode || (w && w.login && w.login.chosen) || "none";
        const things = n === 1 ? _t("1 thing") : _t("%s things", n);
        if (mode !== "email" || !address) {
            return rich(_t("%(first)s has no email sign-in, so no welcome link is sent. The %(things)s to finish wait on My Payobook for when they sign in."),
                        { first: this.first, things });
        }
        if (this.nh.data && this.nh.data.mail_on === false) {
            return rich(_t("This site does not send email: copy the welcome link from New joiners and send it to %(first)s yourself (%(things)s to finish)."),
                        { first: this.first, things });
        }
        return rich(_t("%(first)s gets the welcome link with %(things)s to finish, at %(address)s."),
                    { first: this.first, things }, { address });
    }
    /** The next three things of step 6's timeline (after the first day's own row). */
    get head() {
        const w = this.nh.welcome;
        return ((w && w.timeline) || []).filter((e) => e.id !== "day" && e.id !== "trial").slice(0, 3);
    }
    get sendLabel() {
        return this.approval.needs ? _t("Send for approval") : _t("Add %s", this.first);
    }
    get launchTitle() {
        if (this.approval.problem) {
            return _t("This hire cannot be sent yet");
        }
        if (this.api.ready && docGapsOf(this.nh).length) {
            return _t("One more thing in step 5");
        }
        if (this.api.ready && ownMissingOf(this.nh).length) {
            return _t("One more thing in step 6");
        }
        return this.api.ready ? _t("Ready to send") : _t("The three required steps still need you");
    }
    get launchLine() {
        if (this.approval.problem) {
            return this.approval.problem;
        }
        if (!this.api.ready) {
            return _t("Finish the steps marked in amber on the left, then come back.");
        }
        if (docGapsOf(this.nh).length) {
            return _t("A row you have is not finished. Finish it in step 5, then send.");
        }
        if (ownMissingOf(this.nh).length) {
            return _t("Some of your own fields are required. Fill them in step 6, then send.");
        }
        return this.approval.needs
            ? _t("After sending you can still withdraw it and change it, until it is approved.")
            : _t("Nobody needs to approve new hires here, so the person is added when you press the button.");
    }
    get heading() { return _t("Check, then add %s", this.first); }
    get intro() {
        return this.approval.needs
            ? _t("One last look. A second person approves every new hire, so nothing is created until they agree.")
            : _t("One last look. The person is added as soon as you press the button.");
    }
    get canSend() { return this.api.sendable && !this.approval.problem && !this.nh.sending; }
    get refusal() { return this.nh.refusal; }
    refusalGo() {
        const r = this.refusal;
        if (r && r.step && r.step !== "check") {
            this.api.go(r.step, r.field);
        }
    }

    // ------------------------------------------------------------ after sending
    get doneTitle() {
        const r = this.result;
        if (r.applied) {
            return _t("%s is added", this.name);
        }
        return r.with_whom
            ? _t("%(name)s is with %(who)s for approval", { name: this.name, who: r.with_whom })
            : _t("%s is waiting for approval", this.name);
    }
    get doneLine() {
        return this.result.applied
            ? _t("The employee record and a running contract are ready.")
            : _t("Nothing is created until the hire is approved. Then the record and the running contract are created by themselves.");
    }
    get reference() { return this.result && this.result.reference ? _t("Reference %s", this.result.reference) : ""; }
    get openLabel() { return _t("Open %s's record", this.first); }

    // ------------------------------------------------------------ the welcome legs
    get legs() { return (this.result && this.result.result && this.result.result.legs) || []; }
    get legsOk() { return this.legs.length && this.legs.every((l) => l.ok); }
    get legsFailed() { return this.legs.filter((l) => !l.ok); }
    get legsLine() {
        const r = this.result && this.result.result;
        return (r && r.legs_summary) || "";
    }
    // ------------------------------------------------------------ what was asked (P3b)
    async loadCard(empId) {
        this.card.busy = true;
        try {
            const res = await this.api.inviteCard(empId);
            this.card.data = res || null;
        } catch {
            this.card.data = null;          // the list from the screen still shows
        } finally {
            this.card.busy = false;
        }
    }
    /** `[{key, label, need, state}]`: the server's rows once added, else what the screen asked. */
    get askedRows() {
        const asked = this.card.data && this.card.data.asked;
        if (asked && asked.items) {
            return asked.items;
        }
        return docAskedOf(this.nh).map((a) => ({ ...a, state: "open" }));
    }
    get askedIcons() {
        return Object.fromEntries(docAskedOf(this.nh).map((a) => [a.key, a.icon]));
    }
    askedIcon(row) { return this.askedIcons[row.key] || "fileText"; }
    get askedTitle() { return _t("What %s has been asked for", this.first); }
    get askedChip() {
        const rows = this.askedRows;
        const done = rows.filter((r) => r.state === "done").length;
        return _t("%(done)s of %(total)s done", { done, total: rows.length });
    }
    askedState(row) {
        if (row.state === "done") {
            return { cls: "pbnh-chip--ok", icon: "check", text: _t("Done") };
        }
        if (row.state === "waiting") {
            return { cls: "pbnh-chip--p", icon: "hourglass", text: _t("Sent, waiting for HR") };
        }
        return { cls: "pbnh-chip--warn", icon: "clock", text: _t("Waiting for %s", this.first) };
    }
    needText(row) { return row.need === "first_pay" ? _t("Needed before first pay") : row.need === "joining" ? _t("Asked at joining") : _t("Optional"); }
    get remindRow() {
        const on = this.d.remind !== false;
        return on
            ? { b: _t("Reminders every 2 days"), s: _t("You are told if anything needed for pay is still missing 3 days before %s.", fmtDay(this.d.date_start)) }
            : { b: _t("No reminders"), s: _t("Send the link again from New joiners when you want to chase these.") };
    }
    get canCopy() {
        const a = this.card.data && this.card.data.asked;
        return Boolean(this.result && this.result.applied && a && a.can_copy);
    }
    async copyLink() {
        if (this.card.busy) {
            return;
        }
        this.card.busy = true;
        try {
            const res = await this.api.copyLink(this.result.employee_id);
            if (!res || !res.ok) {
                this.api.toast((res && res.message) || _t("The link could not be copied."), { kind: "error" });
                return;
            }
            this.card.hint = res.expires_hint || "";
            const copied = await copyText(res.link);
            if (copied) {
                this.card.link = "";
                this.api.toast(_t("Link copied. %s", res.expires_hint || ""));
            } else {
                // no clipboard here: show the link to select and copy by hand
                this.card.link = res.link;
            }
        } catch (e) {
            this.api.toast(errorText(e), { kind: "error" });
        } finally {
            this.card.busy = false;
        }
    }
    selectLink(ev) { ev.target.select(); }

    // ------------------------------------------------------------ P8 D: the sign-in slip
    /** Added without an email, signing in with their employee number, and
     *  the reader manages access: a new slip can be made and printed. */
    get canSlip() {
        const f = (this.nh.data && this.nh.data.features) || {};
        const w = this.nh.welcome;
        const mode = this.d.login_mode || (w && w.login && w.login.chosen) || "none";
        return Boolean(this.result && this.result.applied && f.slips && mode === "code"
                       && this.legs.some((l) => l.key === "login" && l.ok));
    }
    async makeSlip() {
        if (this.card.slipBusy) {
            return;
        }
        this.card.slipBusy = true;
        try {
            const res = await this.api.orm.call("pb.access", "reissue_sign_in_slips", [[this.result.employee_id]]);
            this.card.slip = res && res.created && res.created.length ? res : null;
            if (!this.card.slip) {
                this.api.toast((res && res.message) || _t("The slip could not be made."), { kind: "error" });
            }
        } catch (e) {
            this.api.toast(errorText(e), { kind: "error" });
        } finally {
            this.card.slipBusy = false;
        }
    }
    printSlip() {
        printSignInSlips(this.card.slip, { add: (msg, opts) => this.api.toast(msg, { kind: (opts && opts.type) || "info" }) });
    }

    get canSeeJoiners() {
        const f = (this.nh.data && this.nh.data.features) || {};
        return Boolean(this.result && this.result.applied && f.joiners
                       && this.legs.some((l) => l.key === "case" && l.ok));
    }
}
