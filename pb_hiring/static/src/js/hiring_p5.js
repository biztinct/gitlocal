/** @odoo-module **/
/**
 * RECRUIT P5 — interviews and scorecards on the Hiring board and set-up.
 *
 * THE HERO IS THE FINALISTS GRID. Every scorecard of every finalist side by
 * side; one click per column decides (Choose / Keep warm / Not this time),
 * with Undo for five seconds; ←/→ walk the columns. Nothing waits for a
 * missing opinion — the column says "2 of 3 in".
 *
 * Also here: the drawer's scorecard grid (rows panellists, columns the
 * questions), "Enter it for them", Remind on the card, the transcript slot,
 * the scorecard and video line in the scheduling sheet, the role's rounds,
 * the toast that names the Calendly email (or says where to add the link),
 * and Hiring set-up's Scorecards editor + scheduling links + Google.
 *
 * A PATCH, like P3 and P4. Nothing here decides who may do what: the server
 * refuses every verb it should (`_require_recruit`, `_require_write`,
 * `_require_move`); this file only draws and asks.
 */
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { useRef } from "@odoo/owl";
import { useSortable } from "@web/core/utils/sortable_owl";
import { PbHiringBoard } from "./hiring_board";
import { PbHiringSetup } from "./hiring_setup";

const TOAST_MS = 5000;
const SOURCES = [_t("Slack message"), _t("Phone call"), _t("Email"), _t("In person")];
const DECISION_ICON = { yes: "checkCircle", maybe: "helpCircle", no: "xCircle", hold: "pause" };
const KIND_ICON = { text: "pencil", rating: "star", line: "hash", yes_no: "checkCheck" };

function readFile(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result).split(",")[1] || "");
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

// =========================================================================
//  The board
// =========================================================================
patch(PbHiringBoard.prototype, {
    setup() {
        super.setup(...arguments);
        Object.assign(this.state, {
            compare: null, proxy: null, p5Transcript: {}, p5Busy: false,
        });
        this.p5Sources = SOURCES;
    },

    decisionIcon(key) { return DECISION_ICON[key] || "circle"; },
    kindIcon(key) { return KIND_ICON[key] || "circle"; },
    // OWL templates see no `String`/`Number` (only Math, Object, Array, Date…).
    sameId(a, b) { return String(a) === String(b); },
    num(x) { return Number(x) || 0; },
    stars(n) { return [1, 2, 3, 4, 5].map((i) => i <= Math.round(Number(n) || 0)); },

    async call5(verb, payload) {
        try {
            return await this.orm.call("pb.hiring", "act", [verb, payload || {}]);
        } catch (e) {
            this.fail(e);
            return null;
        }
    },

    // ------------------------------------------------ the toast (Calendly)
    showToast(res) {
        super.showToast(res);
        if (this.state.toast && res && res.warning) {
            this.state.toast.warning = res.warning;
            clearTimeout(this._toastTimer);
            // A warning stays until it is read and dismissed or acted on.
            this._toastTimer = setTimeout(() => { this.state.toast = null; }, TOAST_MS * 3);
        }
    },

    async fixSchedulingLink(warning) {
        this.closeToast();
        if (warning && warning.mine) {
            await this.act("open_my_link", {}, { reload: false });
            return;
        }
        this.openSetup();
    },

    // ---------------------------------------------------- the card: Remind
    async remindCard(card) {
        if (!card.remind) { return; }
        const res = await this.call5("remind_opinion", { feedback_id: card.remind.feedback_id });
        if (!res) { return; }
        if (res.link) {
            this.notif.add(res.link, { type: "info", sticky: true, title: _t("Their own link") });
        }
        this.undoableToast(res.note, null);
    },

    // ------------------------------------------------------- the Next box
    async runNextBox(box, which = "main") {
        const step = which === "main" ? box : box.secondary;
        if (step && step.verb === "proxy_open") {
            await this.openProxy(step.payload.feedback_id);
            return;
        }
        return super.runNextBox(box, which);
    },

    // ------------------------------------------- the drawer's scorecards
    partValue(fr, pt) {
        const v = (fr.answers || {})[String(pt.id)];
        return v === undefined || v === null ? "" : v;
    },
    partWords(fr, pt) {
        const v = this.partValue(fr, pt);
        if (v === "") { return "—"; }
        if (pt.kind === "yes_no") { return v === "yes" ? _t("Yes") : _t("No"); }
        if (pt.kind === "line") { return `${v} / 5`; }
        return String(v);
    },
    opinionLine(fr) {
        if (fr.hidden) { return _t("Hidden until everyone is in"); }
        if (fr.state === "submitted") { return ""; }
        if (fr.late) {
            if (!fr.reminded) { return _t("late"); }
            return fr.reminded === 1 ? _t("late · reminded once") : _t("late · reminded %s times", fr.reminded);
        }
        if (fr.state === "pending") { return _t("not yet"); }
        return _t("not asked any more");
    },
    inLabel(sc) { return _t("%(in)s of %(total)s in", { in: sc.in || 0, total: sc.total || 0 }); },

    async remindRow(fr) {
        const res = await this.call5("remind_opinion", { feedback_id: fr.id });
        if (!res) { return; }
        if (res.link) { this.notif.add(res.link, { type: "info", sticky: true, title: _t("Their own link") }); }
        this.undoableToast(res.note, null);
        if (this.state.cand) { await this.openCand(this.state.cand.id, { quiet: true }); }
    },

    // ------------------------------------------------ Enter it for them
    async openProxy(feedbackId) {
        let form;
        try {
            form = await this.orm.call("pb.hiring", "get_feedback_form", [feedbackId]);
        } catch (e) { this.fail(e); return; }
        const answers = {};
        for (const pt of form.parts) { answers[pt.id] = pt.value === null || pt.value === undefined ? "" : pt.value; }
        this.state.proxy = { ...form, answers, source: "", decision: form.decision || "", notes: form.notes || "", missing: [] };
    },
    closeProxy() { this.state.proxy = null; },
    proxyTitle() { return _t("Enter %s's opinion", (this.state.proxy && this.state.proxy.who) || ""); },
    proxySaveLabel() { return _t("Save for %s", (this.state.proxy && this.state.proxy.who) || ""); },
    setProxy(ptId, value) {
        const p = this.state.proxy;
        if (!p) { return; }
        p.answers[ptId] = p.answers[ptId] === value ? "" : value;
        p.missing = p.missing.filter((m) => m !== ptId);
    },
    async saveProxy() {
        const p = this.state.proxy;
        if (!p) { return; }
        const missing = p.parts.filter((pt) => pt.required && (p.answers[pt.id] === "" || p.answers[pt.id] === undefined)).map((pt) => pt.id);
        if (!p.decision) { missing.push("decision"); }
        if (!p.source.trim()) { missing.push("source"); }
        p.missing = missing;
        if (missing.length) {
            this.notif.add(_t("Fill in what is marked, then save."), { type: "warning" });
            return;
        }
        p.busy = true;
        const res = await this.call5("feedback_proxy", {
            feedback_id: p.id, answers: p.answers, decision: p.decision, notes: p.notes, source: p.source,
        });
        p.busy = false;
        if (!res) { return; }
        this.state.proxy = null;
        this.undoableToast(res.note, null);
        if (this.state.view === "role") { await this.reloadRole(); }
        if (this.state.cand) { await this.openCand(this.state.cand.id, { quiet: true }); }
        if (this.state.compare) { await this.loadCompare(); }
    },

    // ------------------------------------------------ the transcript slot
    transcriptDraft(sc) {
        const d = this.state.p5Transcript[sc.interview_id];
        return d === undefined ? ((sc.transcript && sc.transcript.url) || "") : d;
    },
    onTranscriptInput(sc, ev) { this.state.p5Transcript[sc.interview_id] = ev.target.value; },
    async saveTranscript(sc) {
        const url = (this.transcriptDraft(sc) || "").trim();
        const res = await this.call5("transcript_set", { interview_id: sc.interview_id, url });
        if (!res) { return; }
        delete this.state.p5Transcript[sc.interview_id];
        const before = res.before;
        this.undoableToast(res.note, async () => {
            await this.call5("transcript_set", { interview_id: sc.interview_id, url: before });
            if (this.state.cand) { await this.openCand(this.state.cand.id, { quiet: true }); }
        });
        if (this.state.cand) { await this.openCand(this.state.cand.id, { quiet: true }); }
    },
    async uploadTranscript(sc, ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file) { return; }
        const data = await readFile(file);
        const res = await this.call5("transcript_file", { interview_id: sc.interview_id, name: file.name, data });
        ev.target.value = "";
        if (!res) { return; }
        this.undoableToast(res.note, null);
        if (this.state.cand) { await this.openCand(this.state.cand.id, { quiet: true }); }
    },
    async clearTranscriptFile(sc) {
        const res = await this.call5("transcript_clear_file", { interview_id: sc.interview_id });
        if (res) {
            this.undoableToast(res.note, null);
            if (this.state.cand) { await this.openCand(this.state.cand.id, { quiet: true }); }
        }
    },

    // -------------------------------------------- the scheduling sheet
    startSchedule(candidate) {
        super.startSchedule(candidate);
        const form = this.state.scheduling;
        if (!form) { return; }
        Object.assign(form, { scorecard_id: "", scorecards: [], google: null });
        this.loadScheduleDefaults();
    },
    async loadScheduleDefaults() {
        const form = this.state.scheduling;
        if (!form) { return; }
        try {
            const d = await this.orm.call("pb.hiring", "get_schedule_defaults", [form.applicant_id], {
                step_id: form.step_id || false, mode: form.mode,
            });
            if (this.state.scheduling !== form) { return; }
            Object.assign(form, { scorecards: d.scorecards || [], google: d.google || null });
            if (!form.scorecardTouched) { form.scorecard_id = d.scorecard_id ? String(d.scorecard_id) : ""; }
        } catch (e) {
            // The sheet still works without the defaults.
        }
    },
    onScorecardPick(ev) {
        const form = this.state.scheduling;
        if (form) { form.scorecard_id = ev.target.value; form.scorecardTouched = true; }
    },
    /** A2's sheet, plus the scorecard (the same checks, the same verb). */
    async saveSchedule() {
        const form = this.state.scheduling;
        if (!form) { return; }
        if (!form.panel.length) {
            this.notif.add(
                _t("Say who is on the panel — nobody can give an opinion on a conversation they were not in."),
                { type: "warning" });
            return;
        }
        const start = this.toServerTime(form.start);
        if (!start) {
            this.notif.add(_t("Say when it is."), { type: "warning" });
            return;
        }
        const res = await this.act("schedule", {
            applicant_id: form.applicant_id,
            requisition_id: form.requisition_id,
            step_id: form.step_id || false,
            start,
            duration_minutes: Number(form.duration_minutes) || 45,
            mode: form.mode,
            location: form.location,
            panel_employee_ids: form.panel,
            scorecard_id: Number(form.scorecard_id) || false,
        });
        if (res) {
            this.state.scheduling = null;
            if (this.state.view === "role") { await this.reloadRole(); }
            if (this.state.cand) { await this.openCand(this.state.cand.id, { quiet: true }); }
        }
    },
    async connectGoogle() {
        const res = await this.call5("google_connect", { from_url: window.location.href });
        if (res && res.url) { window.location.assign(res.url); }
    },

    // ------------------------------------------------ the role's rounds
    async setRoleFamily(key) {
        const d = this.state.drawer;
        if (!d) { return; }
        const res = await this.call5("role_family", { requisition_id: d.id, family: key || false });
        if (!res) { return; }
        const before = res.before;
        this.undoableToast(res.note, async () => {
            await this.call5("role_family", { requisition_id: d.id, family: before || false });
            await this.reloadRole();
        });
        await this.reloadRole();
    },
    async setRoundScorecard(rd, value) {
        const d = this.state.drawer;
        if (!d) { return; }
        const res = await this.call5("round_scorecard", {
            requisition_id: d.id, step_id: rd.step_id || false, stage_key: rd.stage_key, scorecard_id: Number(value) || false,
        });
        if (!res) { return; }
        const before = res.before;
        const stepId = res.step_id;
        this.undoableToast(res.note, async () => {
            await this.call5("round_scorecard", { requisition_id: d.id, step_id: stepId, scorecard_id: before || false });
            await this.reloadRole();
        });
        await this.reloadRole();
    },
    roundSource(rd) { return rd.picked ? _t("picked for this round") : _t("from the kind of role"); },

    // ======================================================== FINALISTS
    async openCompare() {
        const d = this.state.drawer;
        if (!d) { return; }
        this.state.cand = null;
        this.state.compare = { loading: true, data: null, focus: 0, open: [] };
        await this.loadCompare();
    },
    async loadCompare() {
        const d = this.state.drawer;
        const c = this.state.compare;
        if (!d || !c) { return; }
        try {
            c.data = await this.orm.call("pb.hiring", "get_finalists", [d.id]);
            c.focus = Math.min(c.focus, Math.max(0, c.data.candidates.length - 1));
        } catch (e) {
            this.fail(e);
            this.state.compare = null;
            return;
        } finally {
            if (this.state.compare) { this.state.compare.loading = false; }
        }
    },
    closeCompare() { this.state.compare = null; },
    get compareTitle() {
        const c = this.state.compare;
        return _t("Finalists side by side · %s", (c && c.data && c.data.role) || (this.state.drawer && this.state.drawer.title) || "");
    },
    cmpCols() {
        const c = this.state.compare;
        const n = (c && c.data && c.data.candidates.length) || 1;
        return `grid-template-columns: minmax(150px, 190px) repeat(${n}, minmax(230px, 1fr));`;
    },
    cmpRound(cd, roundNo) {
        return (cd.rounds || []).find((r) => r.round_no === roundNo) || null;
    },
    cmpSlots(roundNo) {
        const c = this.state.compare;
        let n = 0;
        for (const cd of (c && c.data && c.data.candidates) || []) {
            const r = this.cmpRound(cd, roundNo);
            if (r) { n = Math.max(n, r.opinions.length); }
        }
        return Array.from({ length: Math.max(1, n) }, (_x, i) => i);
    },
    cmpOpinion(cd, roundNo, i) {
        const r = this.cmpRound(cd, roundNo);
        return r ? r.opinions[i] || null : null;
    },
    cmpCounts(cd) {
        const labels = { yes: _t("Yes"), maybe: _t("Maybe"), no: _t("No"), hold: _t("Hold") };
        return Object.entries(cd.decision_counts || {}).filter(([, n]) => n).map(([k, n]) => ({ key: k, n, label: labels[k] }));
    },
    cmpIn(cd) { return _t("%(in)s of %(total)s in", { in: cd.in, total: cd.total }); },
    toggleNote(id) {
        const c = this.state.compare;
        if (!c) { return; }
        const at = c.open.indexOf(id);
        if (at === -1) { c.open.push(id); } else { c.open.splice(at, 1); }
    },
    isNoteOpen(id) { return !!(this.state.compare && this.state.compare.open.includes(id)); },
    async decideFinalist(cd, decision) {
        const c = this.state.compare;
        if (!c || !c.data || !c.data.can_decide) { return; }
        const res = await this.call5("finalist_decide", { applicant_id: cd.id, decision });
        if (!res) { return; }
        const from = (res.moved && res.moved[0] && res.moved[0].from_key) || "";
        this.undoableToast(res.note, async () => {
            await this.call5("finalist_undo", {
                applicant_id: cd.id, from_key: from, decision, prev_selected_id: res.prev_selected_id,
            });
            await this.loadCompare();
            await this.reloadRole();
        });
        await this.loadCompare();
        await this.reloadRole();
    },
    cmpOpen(cd) {
        this.state.compare = null;
        this.openCand(cd.id);
    },

    // ---------------------------------------------------------- keyboard
    onKey(ev) {
        const c = this.state.compare;
        if (c) {
            const t = ev.target;
            const typing = t && (t.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName));
            if (ev.key === "Escape") { this.closeCompare(); ev.stopPropagation(); ev.preventDefault(); return; }
            if (typing || this.state.proxy || ev.metaKey || ev.ctrlKey || ev.altKey || !c.data) { return; }
            const list = c.data.candidates;
            if (ev.key === "ArrowRight") { ev.preventDefault(); c.focus = Math.min(c.focus + 1, list.length - 1); this.scrollCmp(); return; }
            if (ev.key === "ArrowLeft") { ev.preventDefault(); c.focus = Math.max(c.focus - 1, 0); this.scrollCmp(); return; }
            const cd = list[c.focus];
            if (!cd || !c.data.can_decide) { return; }
            if (ev.key === "c" || ev.key === "C") { ev.preventDefault(); this.decideFinalist(cd, "choose"); return; }
            if (ev.key === "w" || ev.key === "W") { ev.preventDefault(); this.decideFinalist(cd, "warm"); return; }
            if (ev.key === "n" || ev.key === "N") { ev.preventDefault(); this.decideFinalist(cd, "no"); return; }
            return;
        }
        if (ev.key === "Escape" && this.state.proxy) { this.closeProxy(); ev.stopPropagation(); ev.preventDefault(); return; }
        return super.onKey(ev);
    },
    scrollCmp() {
        const c = this.state.compare;
        const el = document.querySelector(`.pbhr-p5-cmp-col-h[data-i="${c.focus}"]`);
        if (el && el.scrollIntoView) { el.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "smooth" }); }
    },

    get anyDialog() {
        const s = this.state;
        return super.anyDialog || !!(s.compare || s.proxy);
    },
});

// =========================================================================
//  Hiring set-up: Scorecards, scheduling links, Google
// =========================================================================
patch(PbHiringSetup.prototype, {
    setup() {
        super.setup(...arguments);
        Object.assign(this.state, { scPick: null, scPreview: false, scDraft: {}, linkDraft: {} });
        this.scRef = useRef("scParts");
        useSortable({
            enable: () => !!(this.state.data && this.state.data.can_edit && this.scCard),
            ref: this.scRef,
            elements: ".pbhr-p5-part",
            handle: ".pbhr-su-grip",
            cursor: "grabbing",
            placeholderClasses: ["pbhr-su-ph"],
            onDrop: ({ element, previous }) => this.onPartDrop(element, previous),
        });
    },

    get sc() { return (this.state.data && this.state.data.scorecards) || { cards: [], families: [], rounds: [], kinds: [] }; },
    get scCard() {
        const cards = this.sc.cards || [];
        return cards.find((c) => c.id === this.state.scPick) || cards[0] || null;
    },
    kindIcon(key) { return KIND_ICON[key] || "circle"; },
    decisionIcon(key) { return DECISION_ICON[key] || "circle"; },
    scUsed(card) {
        const n = card.rounds_using || 0;
        const i = card.interviews || 0;
        const a = n === 1 ? _t("picked for 1 round") : _t("picked for %s rounds", n);
        return i ? `${a} · ${i === 1 ? _t("1 interview") : _t("%s interviews", i)}` : a;
    },
    scQuestions(card) { return card.n_parts === 1 ? _t("1 question + the decision") : _t("%s questions + the decision", card.n_parts); },

    async openCard(card) {
        if (card.key === "scorecards") {
            const el = document.querySelector(".pbhr-p5-sc-sec");
            if (el && el.scrollIntoView) { el.scrollIntoView({ behavior: "smooth", block: "start" }); }
            return;
        }
        return super.openCard(card);
    },

    pickCard(card) { this.state.scPick = card.id; this.state.scDraft = {}; },

    async scSave(field, value) {
        const card = this.scCard;
        if (!card || !this.state.data.can_edit) { return; }
        if (field === "name" && !String(value || "").trim()) { return; }
        await this.call("scorecard_save", { id: card.id, [field]: value }, {
            undo: (res) => this.call("scorecard_save", { id: card.id, ...res.before }),
        });
    },
    async scDefault() {
        const card = this.scCard;
        if (card) { await this.call("scorecard_save", { id: card.id, is_default: true }); }
    },
    async scNew(copy) {
        const card = this.scCard;
        const res = await this.call("scorecard_new", copy && card ? { copy_of: card.id } : {});
        if (res && res.id) { this.state.scPick = res.id; }
    },
    async scArchive() {
        const card = this.scCard;
        if (!card) { return; }
        const id = card.id;
        await this.call("scorecard_archive", { id }, {
            undo: () => this.call("scorecard_archive", { id, restore: true }),
        });
        this.state.scPick = null;
    },
    async partSave(pt, field, value) {
        if (!this.state.data.can_edit) { return; }
        if (field === "prompt" && !String(value || "").trim()) { return; }
        if (pt[field] === value) { return; }
        await this.call("scorecard_part_save", { part_id: pt.id, [field]: value }, {
            undo: (res) => this.call("scorecard_part_save", { part_id: pt.id, ...res.before }),
        });
    },
    async partAdd(kind) {
        const card = this.scCard;
        if (card) { await this.call("scorecard_part_add", { id: card.id, kind }); }
    },
    async partRemove(pt) {
        await this.call("scorecard_part_remove", { part_id: pt.id }, {
            undo: (res) => this.call("scorecard_part_restore", { saved: res.saved }),
        });
    },
    async onPartDrop(element, previous) {
        const card = this.scCard;
        if (!card) { return; }
        const id = Number(element.dataset.id);
        const ids = card.parts.map((p) => p.id).filter((x) => x !== id);
        const prevId = previous ? Number(previous.dataset.id) : null;
        const at = prevId ? ids.indexOf(prevId) + 1 : 0;
        ids.splice(at, 0, id);
        await this.call("scorecard_reorder", { id: card.id, ids }, {
            undo: (res) => this.call("scorecard_reorder", { id: card.id, ids: res.before }),
        });
    },
    previewStars() { return [1, 2, 3, 4, 5]; },

    // --------------------------------------------- links and Google
    get links() { return (this.state.data && this.state.data.links) || []; },
    get google() { return (this.state.data && this.state.data.google) || {}; },
    linkValue(row) {
        const d = this.state.linkDraft[row.id];
        return d === undefined ? row.link : d;
    },
    onLinkInput(row, ev) { this.state.linkDraft[row.id] = ev.target.value; },
    async saveLink(row) {
        const link = (this.linkValue(row) || "").trim();
        if (link === (row.link || "")) { return; }
        const res = await this.call("scheduling_link_set", { user_id: row.id, link }, {
            undo: (r) => this.call("scheduling_link_set", { user_id: row.id, link: r.before }),
        });
        if (res) { delete this.state.linkDraft[row.id]; }
    },
    canEditLink(row) { return row.me || (this.state.data && this.state.data.can_edit); },
    async connectGoogle() {
        try {
            const res = await this.orm.call("pb.hiring", "act", ["google_connect", { from_url: window.location.href }]);
            if (res && res.url) { window.location.assign(res.url); }
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not work."), { type: "danger" });
        }
    },
    async openGoogleSettings() {
        try {
            const action = await this.orm.call("pb.hiring", "act", ["google_settings", {}]);
            if (action) { await this.action.doAction(action); }
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not work."), { type: "danger" });
        }
    },
});
