/** @odoo-module **/
/**
 * RECRUIT P6 — from signed to joined, on the Hiring board and set-up.
 *
 * THE HERO IS THE COUNTDOWN THAT TICKS ITSELF. A signed offer lands the card
 * in Post-offer with "Joining in 9 days" and a bar that fills; the drawer
 * opens on a ring — one segment per thing on the "Before they join" list —
 * and while it is open it listens (every 15 s, only while somebody outside
 * is being waited on and the tab is visible). When the manager names a
 * buddy from their email, or the new joiner sends their laptop answers, the
 * segment fills, the row ticks with a pop, and a toast says who answered.
 *
 * Also here: Confirm they joined (says exactly what it creates), Did not
 * join (asks why, says who is told), Change the date, a meet-the-team chat,
 * signed documents, and Hiring set-up → Before they join.
 *
 * A PATCH, like P3–P5. Nothing here decides who may do what: the server
 * refuses every verb it should; this file only draws and asks.
 */
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { onWillUnmount, useRef } from "@odoo/owl";
import { useSortable } from "@web/core/utils/sortable_owl";
import { PbHiringBoard } from "./hiring_board";
import { PbHiringSetup } from "./hiring_setup";

const POLL_MS = 15000;
const TICK_MS = 6000;
const RING_C = 2 * Math.PI * 34;
const KIND_ICON = { buddy: "users", laptop: "laptop", chat: "coffee", todo: "checkCircle" };

function readFile(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result).split(",")[1] || "");
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

function pad(n) { return String(n).padStart(2, "0"); }

function isoToday() {
    const d = new Date();
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

// =========================================================================
//  The board
// =========================================================================
patch(PbHiringBoard.prototype, {
    setup() {
        super.setup(...arguments);
        Object.assign(this.state, {
            p6Confirm: null, p6Drop: null, p6Date: null, p6Chat: null, p6Doc: null,
            p6Add: null, p6Busy: false, p6Ticked: [],
        });
        onWillUnmount(() => { clearInterval(this._p6Poll); clearTimeout(this._p6TickTimer); });
        // Hiring numbers → ageing: open the role AND the person.
        const ctx = (this.props.action && this.props.action.context) || {};
        this._p6PendingCand = Number(ctx.pb_cand_id) || null;
    },
    async openRole(id, opts) {
        await super.openRole(id, opts);
        const cand = this._p6PendingCand;
        if (cand) {
            this._p6PendingCand = null;
            await this.openCand(cand);
            this.scrollToCard(cand);
        }
    },

    // ------------------------------------------------------------- the card
    p6Segs(j) {
        const out = [];
        for (let i = 0; i < (j.total || 0); i++) {
            out.push(i < j.done ? "on" : (i < j.done + (j.late || 0) ? "late" : ""));
        }
        return out;
    },

    // ------------------------------------------------------------ the hero
    p6HeroTone(jn) {
        if (jn.state === "joined") { return "is-joined"; }
        if (jn.state === "dropped") { return "is-dropped"; }
        if (jn.days !== null && jn.days < 0) { return "is-overdue"; }
        if (jn.late) { return "is-late"; }
        if (jn.days !== null && jn.days <= 3) { return "is-soon"; }
        return "";
    },
    p6Ring(jn) {
        const n = jn.total || 0;
        if (!n || jn.state !== "signed") {
            const full = jn.state === "joined" || jn.state === "dropped";
            return full ? [{ cls: jn.state === "joined" ? "is-on" : "is-drop", da: `${RING_C} 0`, off: 0 }] : [];
        }
        const gap = n > 1 ? 4 : 0;
        const seg = RING_C / n;
        return jn.items.map((it, i) => ({
            cls: it.state === "done" || it.state === "skipped" ? "is-on" + (this.p6IsTicked(it.id) ? " is-fresh" : "")
                : (it.late ? "is-late" : ""),
            da: `${Math.max(1, seg - gap)} ${RING_C - Math.max(1, seg - gap)}`,
            off: -(i * seg),
        }));
    },
    p6RingTitle(jn) { return _t("%(done)s of %(total)s things ready", { done: jn.done, total: jn.total }); },
    p6When(jn) {
        if (jn.days === null || jn.days === undefined) { return ""; }
        if (jn.days === 0) { return _t("today"); }
        if (jn.days === 1) { return _t("tomorrow"); }
        if (jn.days > 1) { return _t("in %s days", jn.days); }
        return jn.days === -1 ? _t("expected yesterday") : _t("expected %s days ago", -jn.days);
    },
    p6Things(jn) {
        if (!jn.total) { return _t("nothing on the list"); }
        return _t("%(done)s of %(total)s things done", { done: jn.done, total: jn.total });
    },
    p6Live(jn) {
        return jn.state === "signed" && (jn.items || []).some(
            (it) => it.state === "open" && it.sent && (it.owner === "manager" || it.owner === "candidate"));
    },
    p6IsTicked(id) { return this.state.p6Ticked.includes(id); },

    // ------------------------------------------------- listening for answers
    async openCand(id, opts = {}) {
        const before = this.state.cand && this.state.cand.id === id ? this.state.cand.joining : null;
        await super.openCand(id, opts);
        if (before) { this.p6Diff(before, this.state.cand && this.state.cand.joining); }
        this.p6Watch();
    },
    closeCand() {
        clearInterval(this._p6Poll);
        this._p6Poll = null;
        return super.closeCand(...arguments);
    },
    p6Watch() {
        clearInterval(this._p6Poll);
        this._p6Poll = null;
        const cand = this.state.cand;
        if (!cand || !cand.joining || !this.p6Live(cand.joining)) { return; }
        const id = cand.id;
        this._p6Poll = setInterval(async () => {
            if (document.hidden || this.anyDialog || !this.state.cand || this.state.cand.id !== id) { return; }
            try {
                const fresh = await this.orm.silent.call("pb.hiring", "get_candidate", [id]);
                if (!this.state.cand || this.state.cand.id !== id) { return; }
                const before = this.state.cand.joining;
                this.state.cand = fresh;
                if (this.p6Diff(before, fresh.joining, true) && this.state.view === "role") { await this.reloadRole(); }
                if (!fresh.joining || !this.p6Live(fresh.joining)) { clearInterval(this._p6Poll); this._p6Poll = null; }
            } catch {
                // a missed beat is not worth a red toast; the next one tries again
            }
        }, POLL_MS);
    },
    /** Tick what was answered since the last read; say who answered. */
    p6Diff(before, after, announce = false) {
        if (!before || !after) { return false; }
        const was = {};
        for (const it of before.items || []) { was[it.id] = it.state; }
        const fresh = (after.items || []).filter((it) => was[it.id] === "open" && it.state === "done");
        if (!fresh.length) { return false; }
        this.state.p6Ticked = fresh.map((it) => it.id);
        clearTimeout(this._p6TickTimer);
        this._p6TickTimer = setTimeout(() => { this.state.p6Ticked = []; }, TICK_MS);
        const it = fresh[0];
        if (announce) {
            this.undoableToast(it.kind === "buddy" && it.answer
                ? _t("Just now: %s", it.answer)
                : _t("Just now: %(who)s answered — “%(what)s” is ticked.", { who: it.answered_by || _t("they"), what: it.title }), null);
        }
        return true;
    },

    // --------------------------------------------------------------- acting
    async p6Act(verb, payload) {
        this.state.p6Busy = true;
        try {
            const res = await this.orm.call("pb.hiring", "act", [verb, payload || {}]);
            if (res && res.joining && this.state.cand) {
                this.p6Diff(this.state.cand.joining, res.joining);
                this.state.cand.joining = res.joining;
            }
            if (res && res.link) {
                this.notif.add(res.link, { type: "info", sticky: true, title: _t("Their own link") });
            }
            if (res && res.note) {
                const undo = res.undo;
                this.undoableToast(res.note, undo ? async () => {
                    await this.p6Act(undo.verb, { item_id: undo.item_id });
                } : null);
            }
            await this.p6Refresh();
            return res;
        } catch (e) {
            this.fail(e);
            return null;
        } finally {
            this.state.p6Busy = false;
        }
    },
    async p6Refresh() {
        if (this.state.view === "role") { await this.reloadRole(); }
        if (this.state.cand) { await this.openCand(this.state.cand.id, { quiet: true }); }
    },
    get p6Offer() {
        const j = this.state.cand && this.state.cand.joining;
        return j ? j.offer_id : null;
    },

    async p6ItemAction(it) {
        const a = it.action || {};
        if (a.verb === "chat_open") { await this.p6OpenChat(it); return; }
        await this.p6Act(a.verb, { item_id: it.id });
    },
    async p6ItemLink(it) { await this.p6Act("prejoin_link", { item_id: it.id }); },
    async p6ItemDone(it) { await this.p6Act("prejoin_done", { item_id: it.id }); },
    async p6ItemSkip(it) { await this.p6Act("prejoin_skip", { item_id: it.id }); },
    async p6ItemRemove(it) { await this.p6Act("prejoin_remove", { item_id: it.id }); },
    async p6WeekNow() { await this.p6Act("week_send", { offer_id: this.p6Offer }); },

    p6AddOpen() { this.state.p6Add = { title: "", owner: "recruiter", due: "" }; },
    p6AddCancel() { this.state.p6Add = null; },
    p6AddKey(ev) {
        if (ev.key === "Enter") { ev.preventDefault(); this.p6AddSave(); }
        if (ev.key === "Escape") { ev.preventDefault(); ev.stopPropagation(); this.p6AddCancel(); }
    },
    async p6AddSave() {
        const f = this.state.p6Add;
        if (!f || !f.title.trim()) {
            this.notif.add(_t("Say what needs doing."), { type: "warning" });
            return;
        }
        const res = await this.p6Act("prejoin_add", { offer_id: this.p6Offer, title: f.title, owner: f.owner, due: f.due || false });
        if (res) { this.state.p6Add = null; }
    },

    // --------------------------------------------------- the Next box verbs
    async runNextBox(box, which = "main") {
        const step = which === "main" ? box : box.secondary;
        const v = step && step.verb;
        if (v === "confirm_open") { this.p6OpenConfirm(); return; }
        if (v === "drop_open") { this.p6OpenDrop(); return; }
        if (v === "date_open") { this.p6OpenDate(); return; }
        if (v === "chat_open") {
            const jn = this.state.cand && this.state.cand.joining;
            const it = jn && jn.items.find((x) => x.id === (step.payload || {}).item_id);
            await this.p6OpenChat(it || null);
            return;
        }
        if (v === "prejoin_send" || v === "prejoin_done") { await this.p6Act(v, step.payload || {}); return; }
        return super.runNextBox(box, which);
    },

    // -------------------------------------------- from the role's offer panel
    async p6FromOffer(offer, kind) {
        if (!offer || !offer.applicant_id) { return; }
        await this.openCand(offer.applicant_id);
        if (!this.state.cand || !this.state.cand.joining) { return; }
        if (kind === "drop") { this.p6OpenDrop(); } else { this.p6OpenConfirm(); }
    },
    async closeOffer() { await this.p6FromOffer(this.offer, "confirm"); },

    startSigning() {
        super.startSigning(...arguments);
        if (this.state.signing) { this.state.signing.kind = "offer_letter"; }
    },
    /** Signed → the card lands in Post-offer and the drawer opens on it. */
    async saveSigning() {
        const form = this.state.signing;
        if (!form) { return; }
        if (!form.data) {
            this.notif.add(
                _t("Attach the copy they signed. Recording a signature with nothing behind it is the one thing this screen must never let anybody do."),
                { type: "warning" });
            return;
        }
        const res = await this.act("record_signed", { offer_id: this.offer.id, ...form }, { reload: false });
        if (!res) { return; }
        this.state.signing = null;
        await this.refresh();
        if (this.state.view === "role") {
            this.setRoleTab("board");
            await this.reloadRole();
            if (res.applicant_id) { await this.openCand(res.applicant_id); }
        }
    },

    // ---------------------------------------------------------- the dialogs
    p6Close() {
        Object.assign(this.state, { p6Confirm: null, p6Drop: null, p6Date: null, p6Chat: null, p6Doc: null });
    },
    p6OpenConfirm() {
        const cand = this.state.cand;
        const jn = cand && cand.joining;
        if (!jn) { return; }
        const today = isoToday();
        this.state.p6Confirm = {
            offer_id: jn.offer_id, name: cand.name,
            joined_on: jn.expected && jn.expected < today ? jn.expected : (jn.expected || today),
            buddy: (jn.buddies || [])[0] || "", docs: jn.doc_count || 0,
        };
    },
    async p6SaveConfirm() {
        const f = this.state.p6Confirm;
        if (!f) { return; }
        const res = await this.p6Act("confirm_joined", { offer_id: f.offer_id, joined_on: f.joined_on });
        if (res) { this.state.p6Confirm = null; }
    },
    p6OpenDrop() {
        const cand = this.state.cand;
        const jn = cand && cand.joining;
        if (!jn) { return; }
        this.state.p6Drop = { offer_id: jn.offer_id, name: cand.name, manager: jn.manager,
                              reasons: jn.drop_reasons || [], reason: "", note: "" };
    },
    p6SetDropReason(key) { if (this.state.p6Drop) { this.state.p6Drop.reason = key; } },
    async p6SaveDrop() {
        const f = this.state.p6Drop;
        if (!f) { return; }
        const res = await this.p6Act("did_not_join", { offer_id: f.offer_id, reason: f.reason || "other", note: f.note });
        if (res) { this.state.p6Drop = null; }
    },
    p6OpenDate() {
        const cand = this.state.cand;
        const jn = cand && cand.joining;
        if (!jn) { return; }
        this.state.p6Date = { offer_id: jn.offer_id, name: cand.name, current_words: jn.expected_long,
                              date: jn.expected, reason: "" };
    },
    async p6SaveDate() {
        const f = this.state.p6Date;
        if (!f) { return; }
        const res = await this.p6Act("change_join_date", { offer_id: f.offer_id, date: f.date, reason: f.reason });
        if (res) { this.state.p6Date = null; }
    },
    async p6OpenChat(item) {
        const cand = this.state.cand;
        const jn = cand && cand.joining;
        if (!jn) { return; }
        let people = [];
        try {
            people = (await this.orm.call("pb.hiring", "act", ["chat_people", { offer_id: jn.offer_id }])).people || [];
        } catch (e) { this.fail(e); return; }
        const chat = item && item.chat;
        let start = this.defaultStart();
        if (chat && chat.when) {
            const w = new Date(`${String(chat.when).replace(" ", "T")}Z`);
            start = `${w.getFullYear()}-${pad(w.getMonth() + 1)}-${pad(w.getDate())}T${pad(w.getHours())}:${pad(w.getMinutes())}`;
        }
        const mgr = people.find((p) => p.manager);
        this.state.p6Chat = {
            offer_id: jn.offer_id, item_id: item ? item.id : false, name: cand.name, people, q: "",
            picked: chat ? [...chat.people_ids] : (mgr ? [mgr.id] : []),
            start, minutes: chat ? chat.minutes : 30, mode: chat ? chat.mode : "video",
            where: chat ? (chat.where || "") : "",
            google: !!(cand.google && cand.google.connected),
        };
    },
    p6ChatPeople() {
        const c = this.state.p6Chat;
        if (!c) { return []; }
        const q = (c.q || "").trim().toLowerCase();
        const rows = q ? c.people.filter((p) => `${p.name} ${p.job}`.toLowerCase().includes(q))
            : c.people.filter((p) => p.team || c.picked.includes(p.id));
        return (rows.length || q ? rows : c.people).slice(0, 60);
    },
    p6TogglePerson(id) {
        const c = this.state.p6Chat;
        if (!c) { return; }
        const at = c.picked.indexOf(id);
        if (at === -1) { c.picked.push(id); } else { c.picked.splice(at, 1); }
    },
    p6SetMinutes(n) { if (this.state.p6Chat) { this.state.p6Chat.minutes = n; } },
    p6SetMode(m) { if (this.state.p6Chat) { this.state.p6Chat.mode = m; } },
    async p6SaveChat() {
        const f = this.state.p6Chat;
        if (!f) { return; }
        if (!f.picked.length) { this.notif.add(_t("Say who they will meet."), { type: "warning" }); return; }
        const start = this.toServerTime(f.start);
        if (!start) { this.notif.add(_t("Say when the chat is."), { type: "warning" }); return; }
        const res = await this.p6Act("chat_save", {
            offer_id: f.offer_id, item_id: f.item_id || false, start, minutes: f.minutes,
            mode: f.mode, where: f.where, people_ids: f.picked,
        });
        if (res) { this.state.p6Chat = null; }
    },
    p6OpenDoc() {
        const jn = this.state.cand && this.state.cand.joining;
        if (!jn) { return; }
        const missing = ((jn.doc_set && jn.doc_set.rows) || []).find((r) => !r.have);
        this.state.p6Doc = { offer_id: jn.offer_id, kinds: jn.doc_kinds || [], kind: missing ? missing.kind : "other",
                             label: "", signed_on: isoToday(), data: "", filename: "", mimetype: "",
                             joined: jn.state === "joined" };
    },
    async p6DocFile(ev) {
        const file = ev.target.files && ev.target.files[0];
        const f = this.state.p6Doc;
        if (!file || !f) { return; }
        if (file.size > 5 * 1024 * 1024) {
            this.notif.add(_t("That file is bigger than 5 MB. A scan is usually well under that."), { type: "warning" });
            ev.target.value = "";
            return;
        }
        f.data = await readFile(file);
        f.filename = file.name;
        f.mimetype = file.type;
    },
    async p6SaveDoc() {
        const f = this.state.p6Doc;
        if (!f || !f.data) { return; }
        const res = await this.p6Act("doc_add", {
            offer_id: f.offer_id, kind: f.kind, label: f.label, signed_on: f.signed_on,
            data: f.data, filename: f.filename, mimetype: f.mimetype,
        });
        if (res) { this.state.p6Doc = null; }
    },
    async p6DocRemove(dc) {
        if (!window.confirm(_t("Remove “%s” from this offer?", dc.label))) { return; }
        await this.p6Act("doc_remove", { offer_id: this.p6Offer, doc_id: dc.id });
    },

    // ------------------------------------------------------------- keyboard
    get anyDialog() {
        const s = this.state;
        return super.anyDialog || !!(s.p6Confirm || s.p6Drop || s.p6Date || s.p6Chat || s.p6Doc);
    },
    onKey(ev) {
        const s = this.state;
        if (ev.key === "Escape" && (s.p6Confirm || s.p6Drop || s.p6Date || s.p6Chat || s.p6Doc)) {
            this.p6Close();
            ev.stopPropagation();
            ev.preventDefault();
            return;
        }
        return super.onKey(ev);
    },
});

// =========================================================================
//  Hiring set-up → Before they join
// =========================================================================
patch(PbHiringSetup.prototype, {
    setup() {
        super.setup(...arguments);
        this.p6Ref = useRef("p6tpl");
        useSortable({
            enable: () => !!(this.state.data && this.state.data.can_edit),
            ref: this.p6Ref,
            elements: ".pbhr-p6-tpl",
            handle: ".pbhr-su-grip",
            cursor: "grabbing",
            placeholderClasses: ["pbhr-su-ph"],
            onDrop: ({ element, previous }) => this.p6TplDrop(element, previous),
        });
    },
    get p6Rows() { return ((this.state.data && this.state.data.prejoin) || { items: [] }).items; },
    p6KindIcon(kind) { return KIND_ICON[kind] || "circle"; },
    async openCard(card) {
        if (card.key === "prejoin") {
            const el = document.querySelector(".pbhr-su-p6");
            if (el && el.scrollIntoView) { el.scrollIntoView({ behavior: "smooth", block: "start" }); }
            return;
        }
        return super.openCard(card);
    },
    async p6TplSave(row, field, value) {
        if (field === "title" && !String(value || "").trim()) { return; }
        await this.call("prejoin_tpl_save", { id: row.id, [field]: value }, {
            undo: (res) => this.call("prejoin_tpl_save", { id: row.id, ...res.before }),
        });
    },
    async p6TplDays(row, value) {
        const n = Math.abs(parseInt(value, 10) || 0);
        await this.p6TplSave(row, "days", -n);
    },
    async p6TplRemove(row) {
        await this.call("prejoin_tpl_remove", { id: row.id }, {
            undo: () => this.call("prejoin_tpl_restore", { id: row.id }),
        });
    },
    async p6TplAdd(kind) { await this.call("prejoin_tpl_add", { kind }); },
    async p6TplDrop(element, previous) {
        const id = Number(element.dataset.id);
        const ids = this.p6Rows.map((r) => r.id).filter((x) => x !== id);
        const prevId = previous ? Number(previous.dataset.id) : null;
        const at = prevId ? ids.indexOf(prevId) + 1 : 0;
        ids.splice(at, 0, id);
        await this.call("prejoin_tpl_reorder", { ids }, {
            undo: (res) => this.call("prejoin_tpl_reorder", { ids: res.before }),
        });
    },
});
