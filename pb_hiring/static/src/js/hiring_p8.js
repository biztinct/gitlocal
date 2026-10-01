/** @odoo-module **/
/**
 * RECRUIT P8 — Hiring set-up → Emails and languages, and Automations.
 *
 * Emails: every candidate email as a row with "when it goes" and a chip per
 * language; the editor has English / Tiếng Việt / Bahasa tabs (each tab its
 * own draft), detail chips that insert `{{token}}` where the cursor is, the
 * email drawn live as the candidate will get it (the server renders it, so
 * a wrong detail shows its sentence here and never in an inbox), "Send me a
 * test" and "Reset to the standard text". Ctrl/⌘+S saves, Esc closes.
 *
 * Automations: the hero is the sentence. The talent lead's own rules and the
 * built-in ones in one list; "Add a rule" builds the sentence from four
 * pickers and shows it live; "Try it on a candidate" says exactly what would
 * happen before anything is switched on; the run log says what did.
 */
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { markup, onWillUnmount } from "@odoo/owl";
import { PbHiringSetup } from "./hiring_setup";
import { PbHiringBoard } from "./hiring_board";

const LANG_SHORT = { en_US: "EN", vi_VN: "VI", id_ID: "ID" };

const CLAUSE = {
    applied: "somebody applies", stage_entered: "a candidate enters %(stage)s",
    stage_waiting: "a candidate has waited %(days)s in %(stage)s",
    interview_scheduled: "an interview is arranged", interview_done: "an interview is marked done",
    interview_no_show: "nobody came to an interview", opinions_all_in: "every opinion on an interview is in",
    documents_complete: "all the papers are in", check_started: "a background check starts",
    offer_sent: "an offer is sent", offer_accepted: "an offer is accepted", offer_declined: "an offer is turned down",
    offer_signed: "an offer is signed", joined: "somebody joins", did_not_join: "somebody who signed will not join",
    request_sent_in: "a hiring request is sent in", request_agreed: "a hiring request is agreed",
    referral_received: "a colleague refers somebody", agency_submitted: "an agency puts somebody forward",
};

function fill(text, values) {
    return text.replace(/%\((\w+)\)s/g, (_m, k) => values[k] ?? "");
}

function days(n) { return n === 1 ? _t("1 day") : _t("%s days", n); }

function blankRule() {
    return {
        id: false, event: "stage_entered", stage_id: false, days: 3, action: "send_email",
        template_key: "", recipient: "candidate", custom_emails: "", message_subject: "",
        message_body: "", todo_text: "", target_stage_id: false, tag_id: false, tag: "",
        delay_hours: 0, once: true, department_ids: [], country_ids: [],
        afterUnit: "now", afterN: 2,
    };
}

patch(PbHiringSetup.prototype, {
    setup() {
        super.setup(...arguments);
        Object.assign(this.state, {
            p8Ed: null, p8Rule: null, p8Tab: "rules", p8Try: null, p8ShowInternal: false,
            p8ResetAsk: false, p8DelAsk: null,
        });
        this._p8Keys = (ev) => this.p8OnKey(ev);
        window.addEventListener("keydown", this._p8Keys, { capture: true });
        onWillUnmount(() => {
            window.removeEventListener("keydown", this._p8Keys, { capture: true });
            clearTimeout(this._p8PrevTimer);
            clearTimeout(this._p8TryTimer);
        });
    },

    // =================================================================
    //  The cards
    // =================================================================
    async openCard(card) {
        const at = { emails: ".pbhr-su-p8em", automations: ".pbhr-su-p8au" }[card.key];
        if (at) {
            const el = document.querySelector(at);
            if (el && el.scrollIntoView) { el.scrollIntoView({ behavior: "smooth", block: "start" }); }
            return;
        }
        return super.openCard(card);
    },

    p8OnKey(ev) {
        const ed = this.state.p8Ed;
        const open = ed || this.state.p8Rule;
        if (!open) { return; }
        if (ev.key === "Escape") {
            ev.preventDefault(); ev.stopPropagation();
            if (ed) { this.p8CloseEditor(); } else { this.state.p8Rule = null; }
            return;
        }
        if ((ev.ctrlKey || ev.metaKey) && (ev.key === "s" || ev.key === "S")) {
            ev.preventDefault(); ev.stopPropagation();
            if (ed) { this.p8SaveEmail(); } else { this.p8SaveRule(); }
        }
    },

    // =================================================================
    //  Emails and languages
    // =================================================================
    get p8Em() { return (this.state.data && this.state.data.emails) || { rows: [], internal: [], langs: ["en_US"], lang_words: {} }; },

    p8LangShort(lg) { return LANG_SHORT[lg] || lg; },

    p8LangWord(lg) { return (this.p8Em.lang_words || {})[lg] || lg; },

    p8ChipTitle(row, lg) {
        return row.langs[lg] === "ok"
            ? _t("%s: written. Click to read or change it.", this.p8LangWord(lg))
            : _t("%s: missing — English goes instead. Click to write it.", this.p8LangWord(lg));
    },

    p8OpenEmail(row, lang = "en_US") {
        if (!row) { return; }
        const drafts = {};
        for (const lg of this.p8Em.langs) {
            const t = row.texts[lg] || { subject: "", body: "", button: "" };
            drafts[lg] = { subject: t.subject || "", body: t.body || "", button: t.button || "", dirty: false };
        }
        this.state.p8Ed = { id: row.id, key: row.key, lang, drafts, preview: null, busy: false, lastField: "body" };
        this.state.p8ResetAsk = false;
        this.p8Preview();
    },

    p8OpenEmailById(id, lang = "en_US") {
        const row = this.p8Em.rows.find((r) => r.id === id);
        if (row) { this.p8OpenEmail(row, lang); }
    },

    get p8EdRow() {
        const ed = this.state.p8Ed;
        return ed ? this.p8Em.rows.find((r) => r.id === ed.id) : null;
    },

    get p8Draft() {
        const ed = this.state.p8Ed;
        return ed ? ed.drafts[ed.lang] : null;
    },

    get p8Dirty() {
        const ed = this.state.p8Ed;
        return !!ed && Object.values(ed.drafts).some((d) => d.dirty);
    },

    p8DirtyLangs() {
        const ed = this.state.p8Ed;
        return ed ? Object.keys(ed.drafts).filter((lg) => ed.drafts[lg].dirty) : [];
    },

    p8CloseEditor() {
        if (this.p8Dirty && !this.state.p8Ed.confirmClose) {
            this.state.p8Ed.confirmClose = true;
            return;
        }
        this.state.p8Ed = null;
    },

    p8SetLang(lg) {
        this.state.p8Ed.lang = lg;
        this.state.p8ResetAsk = false;
        this.p8Preview();
    },

    p8Edit(field, value) {
        const d = this.p8Draft;
        d[field] = value;
        d.dirty = true;
        this.state.p8Ed.confirmClose = false;
        this.p8Preview();
    },

    p8Focus(field) { if (this.state.p8Ed) { this.state.p8Ed.lastField = field; } },

    p8Insert(token) {
        const ed = this.state.p8Ed;
        const field = ed.lastField === "subject" ? "subject" : "body";
        const el = document.querySelector(field === "subject" ? ".pbhr-p8-subject" : ".pbhr-p8-body");
        const text = `{{${token}}}`;
        const d = this.p8Draft;
        let value = d[field] || "";
        if (el && typeof el.selectionStart === "number") {
            const at = el.selectionStart;
            value = value.slice(0, at) + text + value.slice(el.selectionEnd);
            this.p8Edit(field, value);
            requestAnimationFrame(() => { el.focus(); el.selectionStart = el.selectionEnd = at + text.length; });
        } else {
            this.p8Edit(field, value + text);
        }
    },

    p8Preview() {
        clearTimeout(this._p8PrevTimer);
        this._p8PrevTimer = setTimeout(() => this.p8LoadPreview(), 350);
    },

    async p8LoadPreview() {
        const ed = this.state.p8Ed;
        if (!ed) { return; }
        const d = ed.drafts[ed.lang];
        const missingLang = !d.subject && !d.body && ed.lang !== "en_US";
        try {
            const res = await this.orm.call("pb.hiring", "get_email_preview",
                [ed.id, missingLang ? "en_US" : ed.lang, missingLang ? null : d.subject,
                    missingLang ? null : d.body, missingLang ? null : d.button]);
            if (this.state.p8Ed && this.state.p8Ed.id === ed.id) {
                this.state.p8Ed.preview = Object.assign(res, {
                    fallback: missingLang, html_markup: res.ok ? markup(res.html) : "",
                });
            }
        } catch (e) {
            if (this.state.p8Ed) {
                this.state.p8Ed.preview = { ok: false, error: (e && e.data && e.data.message) || _t("The preview could not be drawn.") };
            }
        }
    },

    async p8SaveEmail() {
        const ed = this.state.p8Ed;
        if (!ed || ed.busy || !this.p8Dirty) { return; }
        ed.busy = true;
        const saved = [];
        for (const lg of this.p8DirtyLangs()) {
            const d = ed.drafts[lg];
            const res = await this.call("email_save", { id: ed.id, lang: lg, subject: d.subject, body: d.body, button: d.button }, {
                undo: (r) => this.call("email_restore", { id: ed.id, lang: lg, before: r.before }).then(() => this.p8Refresh()),
            });
            if (!res) { ed.busy = false; this.state.p8Ed.lang = lg; return; }
            saved.push(lg);
            d.dirty = false;
        }
        ed.busy = false;
        if (saved.length > 1) {
            this.toast(_t("Saved in %s languages. The next email goes out with these words.", saved.length), null);
        }
        this.p8Refresh();
    },

    p8Refresh() {
        // Keep the editor on the same email with the server's words.
        const ed = this.state.p8Ed;
        if (!ed) { return; }
        const row = this.p8EdRow;
        if (!row) { return; }
        for (const lg of Object.keys(ed.drafts)) {
            if (!ed.drafts[lg].dirty) {
                const t = row.texts[lg] || {};
                Object.assign(ed.drafts[lg], { subject: t.subject || "", body: t.body || "", button: t.button || "" });
            }
        }
        this.p8Preview();
    },

    async p8Test() {
        const ed = this.state.p8Ed;
        if (!ed) { return; }
        if (this.p8Dirty) {
            this.notif.add(_t("Save first — the test uses the saved words."), { type: "warning" });
            return;
        }
        const d = ed.drafts[ed.lang];
        const lang = (!d.subject && ed.lang !== "en_US") ? "en_US" : ed.lang;
        await this.call("email_test", { id: ed.id, lang });
    },

    async p8Reset() {
        const ed = this.state.p8Ed;
        if (!ed) { return; }
        this.state.p8ResetAsk = false;
        const row = this.p8EdRow;
        const before = row ? JSON.parse(JSON.stringify(row.texts)) : null;
        await this.call("email_reset", { id: ed.id }, {
            undo: before ? async () => {
                for (const lg of Object.keys(before)) {
                    await this.call("email_restore", { id: ed.id, lang: lg, before: before[lg] });
                }
                this.p8Refresh();
            } : null,
        });
        for (const lg of Object.keys(ed.drafts)) { ed.drafts[lg].dirty = false; }
        this.p8Refresh();
    },

    async p8OpenInternal(row) {
        const action = await this.call("email_open_internal", { id: row.id });
        if (action && action.type) { await this.action.doAction(action); }
    },

    p8Tokens() {
        const row = this.p8EdRow;
        return row ? row.tokens : [];
    },

    // =================================================================
    //  Automations
    // =================================================================
    get p8Au() {
        return (this.state.data && this.state.data.automations) || {
            rules: [], builtins: [], log: [], events: [], actions: [], recipients: [], stages: [],
            emails: [], tags: [], departments: [], countries: [], queued: 0,
        };
    },

    get p8MyOn() { return this.p8Au.rules.filter((r) => r.effective).length; },

    get p8HasWaiting() { return this.p8Au.rules.some((r) => r.event === "stage_waiting" && r.active); },

    p8LogIcon(st) { return { done: "checkCircle", skipped: "minusCircle", failed: "alert", queued: "hourglass" }[st] || "circle"; },

    p8LogWord(st) { return { done: _t("Done"), skipped: _t("Skipped"), failed: _t("Did not work"), queued: _t("Waiting") }[st] || st; },

    p8When(stored) {
        if (!stored) { return ""; }
        const when = new Date(`${String(stored).replace(" ", "T")}Z`);
        if (isNaN(when.getTime())) { return String(stored); }
        return when.toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
    },

    async p8Toggle(rule) {
        const on = !rule.active || (rule.seed_key === "calendly" && rule.phone_off);
        await this.call("rule_toggle", { id: rule.id, on }, {
            undo: () => this.call("rule_toggle", { id: rule.id, on: !on }),
        });
    },

    async p8ToggleBuiltin(b) {
        if (b.locked) { return; }
        const on = !b.on;
        await this.call("builtin_switch", { key: b.key, on }, {
            undo: () => this.call("builtin_switch", { key: b.key, on: !on }),
        });
    },

    p8EmailOf(key) { return this.p8Em.rows.find((r) => r.key === key); },

    p8EditBuiltinEmail(b) { this.p8OpenEmailById(b.email_id); },

    p8StartAdd() {
        const r = blankRule();
        const shortlist = this.p8Au.stages.find((s) => s.key === "shortlist");
        r.stage_id = shortlist ? shortlist.id : false;
        r.template_key = (this.p8Au.emails[0] && this.p8Au.emails[0].key) || "";
        this.state.p8Rule = r;
        this.state.p8Try = null;
    },

    p8StartEdit(rule) {
        const r = Object.assign(blankRule(), JSON.parse(JSON.stringify(rule)));
        const h = rule.delay_hours || 0;
        r.afterUnit = !h ? "now" : (h % 24 === 0 ? "days" : "hours");
        r.afterN = !h ? 2 : (h % 24 === 0 ? h / 24 : h);
        this.state.p8Rule = r;
        this.state.p8Try = null;
    },

    p8Ev(key) { return this.p8Au.events.find((e) => e.key === key) || {}; },

    p8StageName(id) { const s = this.p8Au.stages.find((x) => x.id === Number(id)); return s ? s.name : ""; },

    get p8OpenStages() { return this.p8Au.stages.filter((s) => s.key !== "joined"); },

    p8SetAction(key) {
        const r = this.state.p8Rule;
        r.action = key;
        if (key === "todo" && ["candidate", "custom"].includes(r.recipient)) { r.recipient = "recruiter"; }
        if (key === "send_email" && !r.recipient) { r.recipient = "candidate"; }
        if (this.p8Ev(r.event).role_only && r.recipient === "candidate") { r.recipient = "recruiter"; }
    },

    p8SetEvent(key) {
        const r = this.state.p8Rule;
        r.event = key;
        const ev = this.p8Ev(key);
        if (ev.role_only) {
            if (["move_stage", "tag"].includes(r.action)) { r.action = "todo"; }
            if (r.recipient === "candidate") { r.recipient = "recruiter"; }
        }
        if (ev.stage && !r.stage_id) {
            const s = this.p8Au.stages.find((x) => x.key === "shortlist");
            r.stage_id = s ? s.id : false;
        }
    },

    p8Recipients() {
        const r = this.state.p8Rule;
        const ev = this.p8Ev(r.event);
        return this.p8Au.recipients.filter((x) => {
            if (r.action === "todo") { return ["recruiter", "hiring_manager", "talent_lead"].includes(x.key); }
            if (ev.role_only && x.key === "candidate") { return false; }
            return true;
        });
    },

    p8Hours(r) {
        if (r.afterUnit === "now") { return 0; }
        const n = Math.max(1, parseInt(r.afterN, 10) || 1);
        return r.afterUnit === "days" ? n * 24 : n;
    },

    p8ToggleIn(listName, id) {
        const r = this.state.p8Rule;
        const n = Number(id);
        r[listName] = r[listName].includes(n) ? r[listName].filter((x) => x !== n) : [...r[listName], n];
    },

    p8PickScope(listName, ev) {
        if (ev.target.value) { this.p8ToggleIn(listName, ev.target.value); }
        ev.target.value = "";
    },

    p8Name(list, id) { const x = list.find((y) => y.id === id); return x ? x.name : ""; },

    get p8Sentence() {
        const r = this.state.p8Rule;
        if (!r) { return ""; }
        const stage = this.p8StageName(r.stage_id) || _t("a stage");
        let when = fill(CLAUSE[r.event] || "", { stage, days: days(Math.max(1, parseInt(r.days, 10) || 1)) });
        const scope = [];
        if (r.department_ids.length) { scope.push(r.department_ids.map((i) => this.p8Name(this.p8Au.departments, i)).join(", ")); }
        if (r.country_ids.length) { scope.push(r.country_ids.map((i) => this.p8Name(this.p8Au.countries, i)).join(", ")); }
        if (scope.length) { when += ` (${_t("only %s", scope.join(" · "))})`; }
        const whoWord = {
            candidate: _t("the candidate"), recruiter: _t("the recruiter"), hiring_manager: _t("the hiring manager"),
            talent_lead: _t("the talent lead"), custom: r.custom_emails || _t("these addresses"),
        }[r.recipient] || "";
        let then = "…";
        if (r.action === "send_email" && r.recipient === "candidate") {
            const e = this.p8Au.emails.find((x) => x.key === r.template_key);
            then = _t("send “%s” to the candidate", e ? e.name : _t("an email"));
        } else if (r.action === "send_email") {
            then = _t("email %s", whoWord);
        } else if (r.action === "todo") {
            then = _t("give %(who)s a to-do: “%(t)s”", { who: whoWord, t: r.todo_text || "…" });
        } else if (r.action === "move_stage") {
            then = _t("move them to %s", this.p8StageName(r.target_stage_id) || "…");
        } else if (r.action === "tag") {
            const t = this.p8Au.tags.find((x) => x.id === Number(r.tag_id));
            then = _t("tag them “%s”", t ? t.name : (r.tag || "…"));
        }
        const h = this.p8Hours(r);
        const after = !h ? _t("right away") : (h % 24 === 0 ? _t("after %s", days(h / 24)) : (h === 1 ? _t("after 1 hour") : _t("after %s hours", h)));
        return _t("When %(when)s, %(then)s, %(after)s.", { when, then, after });
    },

    p8RulePayload() {
        const r = this.state.p8Rule;
        return {
            id: r.id || false, event: r.event, stage_id: Number(r.stage_id) || false,
            days: parseInt(r.days, 10) || 0, action: r.action, template_key: r.template_key || false,
            recipient: r.recipient, custom_emails: r.custom_emails, message_subject: r.message_subject,
            message_body: r.message_body, todo_text: r.todo_text,
            target_stage_id: Number(r.target_stage_id) || false, tag_id: Number(r.tag_id) || false,
            tag: r.tag, delay_hours: this.p8Hours(r), once: !!r.once,
            department_ids: r.department_ids, country_ids: r.country_ids,
        };
    },

    async p8SaveRule() {
        const r = this.state.p8Rule;
        if (!r || r.busy) { return; }
        r.busy = true;
        r.error = "";
        try {
            const res = await this.orm.call("pb.hiring", "act", ["rule_save", this.p8RulePayload()]);
            this.state.p8Rule = null;
            await this.load();
            if (res && res.note) {
                const before = res.before;
                this.toast(res.note, before ? () => this.call("rule_save", Object.assign({}, before, { once: before.once })) : null);
            }
        } catch (e) {
            if (this.state.p8Rule) {
                this.state.p8Rule.error = (e && e.data && e.data.message) || _t("That rule could not be saved.");
                this.state.p8Rule.busy = false;
            }
        }
    },

    async p8Delete(rule) {
        this.state.p8DelAsk = null;
        await this.call("rule_delete", { id: rule.id }, {
            undo: (res) => this.call("rule_save", Object.assign({}, res.saved, { id: false })),
        });
    },

    async p8RunWaiting() { await this.call("rules_run_waiting", {}); this.state.p8Tab = "log"; },

    // ------------------------------------------------- try it on a candidate
    p8StartTry(rule = null) {
        if (rule) { this.p8StartEdit(rule); }
        this.state.p8Try = { q: "", list: [], picked: null, result: null, busy: false };
        this.p8Search();
    },

    p8Search() {
        clearTimeout(this._p8TryTimer);
        this._p8TryTimer = setTimeout(async () => {
            const t = this.state.p8Try;
            if (!t) { return; }
            try {
                t.list = await this.orm.call("pb.hiring", "get_rule_candidates", [t.q || ""]);
            } catch {
                t.list = [];
            }
        }, 250);
    },

    async p8Try(c) {
        const t = this.state.p8Try;
        t.picked = c;
        t.busy = true;
        try {
            t.result = await this.orm.call("pb.hiring", "act", ["rule_try", { applicant_id: c.id, rule: this.p8RulePayload() }]);
        } catch (e) {
            t.result = { lines: [{ ok: false, text: (e && e.data && e.data.message) || _t("That could not be tried.") }] };
        }
        t.busy = false;
    },

    p8TryIcon(ok) { return ok === true ? "checkCircle" : (ok === false ? "xCircle" : "info"); },
});

// =========================================================================
//  The board: "Send the on-hold email" on the outcome sheet
// =========================================================================
patch(PbHiringBoard.prototype, {
    async saveOutcome() {
        const o = this.state.outcome;
        if (o && o.key === "on_hold" && o.send_email) {
            this.state.outcome = null;
            await this.moveTo(o.ids, o.key, { reason: o.reason, hold_until: o.hold_until, send_email: true });
            return;
        }
        return super.saveOutcome();
    },
});
