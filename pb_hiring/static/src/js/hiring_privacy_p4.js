/** @odoo-module **/
/**
 * RECRUIT P4 — private until shared, on the Hiring board.
 *
 * THE HERO IS THE SHARE SHEET. Tick "Minh · Hiring manager" and "CV", press
 * Share: the card's chip says "Shared with Minh", the drawer's Shared-with
 * line and its locks change in place (they flash once), and Minh's own board
 * now opens the CV. Every share can be undone for five seconds.
 *
 * A PATCH, like P3: the drawer, the cards, the toast and the selection bar
 * already live in `PbHiringBoard`. Nothing here decides who may see what —
 * the server builds every payload from the reader's parts (`pb.hiring._parts`)
 * and refuses every verb it should; this file only draws and asks.
 */
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PbHiringBoard } from "./hiring_board";

const SEARCH_DEBOUNCE = 250;
const FLASH_MS = 1400;
const TOAST_MS = 5000;
const FACETS = ["skills", "countries", "teams", "tags", "sources"];
const FACET_PICK = { skills: "skill_ids", countries: "country_ids", teams: "team_ids", tags: "tag_ids", sources: "source_ids" };

patch(PbHiringBoard.prototype, {
    // ============================================================ the toast
    /** A toast whose Undo runs `undo` (a share, a note, a tag). */
    undoableToast(text, undo) {
        clearTimeout(this._toastTimer);
        this.state.toast = { text, moved: [], prompt: null, undo: undo || null };
        this._toastTimer = setTimeout(() => { this.state.toast = null; }, TOAST_MS);
    },

    async call4(verb, payload) {
        try {
            return await this.orm.call("pb.hiring", "act", [verb, payload || {}]);
        } catch (e) {
            this.fail(e);
            return null;
        }
    },

    /** Re-read the role and the open drawer, then flash what changed. */
    async afterShare(ids) {
        if (this.state.view === "role") { await this.reloadRole(); }
        if (this.state.cand) { await this.openCand(this.state.cand.id, { quiet: true }); }
        this.state.shareFlash = ids || [];
        clearTimeout(this._flashTimer);
        this._flashTimer = setTimeout(() => { this.state.shareFlash = []; }, FLASH_MS);
    },

    isFlash(id) { return (this.state.shareFlash || []).includes(id); },

    // ======================================================== the share sheet
    async openShare(ids) {
        const list = (ids || []).filter(Boolean);
        if (!list.length) { return; }
        const reqId = this.state.drawer ? this.state.drawer.id : false;
        let opts;
        try {
            opts = await this.orm.call("pb.hiring", "get_share_options", [], {
                requisition_id: reqId, applicant_ids: list,
            });
        } catch (e) { this.fail(e); return; }
        const current = opts.current || {};
        const picked = Object.keys(current).filter((k) => current[k].all).map(Number);
        let parts = [...(opts.defaults || [])];
        if (picked.length) {
            const union = new Set();
            for (const k of picked) { for (const p of current[k].parts) { union.add(p); } }
            parts = (opts.parts || []).map((p) => p.key).filter((k) => union.has(k));
        }
        this.state.shareSheet = {
            ids: list, people: opts.people || [], parts: opts.parts || [], role: opts.role || "",
            picked, was: [...picked], partsPicked: parts, q: "", results: [], note: "", busy: false,
        };
    },

    closeShare() { this.state.shareSheet = null; },

    sharePicked(p) { return this.state.shareSheet.picked.includes(p.user_id); },

    toggleSharePerson(p) {
        const s = this.state.shareSheet;
        if (p.portal) { return; }
        s.picked = s.picked.includes(p.user_id) ? s.picked.filter((i) => i !== p.user_id) : [...s.picked, p.user_id];
        if (!s.people.some((x) => x.user_id === p.user_id)) { s.people = [...s.people, p]; }
    },

    sharePartOn(key) { return this.state.shareSheet.partsPicked.includes(key); },

    toggleSharePart(key) {
        const s = this.state.shareSheet;
        s.partsPicked = s.partsPicked.includes(key) ? s.partsPicked.filter((k) => k !== key) : [...s.partsPicked, key];
    },

    onShareQuery(ev) {
        const s = this.state.shareSheet;
        s.q = ev.target.value;
        clearTimeout(this._shareTimer);
        this._shareTimer = setTimeout(async () => {
            if (!this.state.shareSheet) { return; }
            try {
                const rows = await this.orm.call("pb.hiring", "share_people", [s.q], {
                    requisition_id: this.state.drawer ? this.state.drawer.id : false,
                });
                const known = new Set(s.people.map((p) => p.user_id));
                this.state.shareSheet.results = rows.filter((r) => !known.has(r.user_id));
            } catch (e) { this.fail(e); }
        }, SEARCH_DEBOUNCE);
    },

    addShareResult(p) {
        const s = this.state.shareSheet;
        s.people = [...s.people, p];
        s.picked = [...s.picked, p.user_id];
        s.results = s.results.filter((r) => r.user_id !== p.user_id);
        s.q = "";
    },

    get sharePreview() {
        const s = this.state.shareSheet;
        if (!s) { return ""; }
        const names = s.people.filter((p) => s.picked.includes(p.user_id)).map((p) => p.name);
        if (!names.length) { return _t("Nobody outside the hiring team will see this person."); }
        const words = s.parts.filter((p) => s.partsPicked.includes(p.key)).map((p) => p.label);
        if (!words.length) { return _t("%s will see the name, the stage and interview dates only.", names.join(", ")); }
        return _t("%(who)s will see: %(what)s.", { who: names.join(", "), what: words.join(", ") });
    },

    get shareTitle() {
        const s = this.state.shareSheet;
        if (!s) { return ""; }
        if (s.ids.length === 1) {
            const c = (this.state.cand && this.state.cand.id === s.ids[0]) ? this.state.cand : this.cardById(s.ids[0]);
            return _t("Share %s with…", (c && c.name) || "");
        }
        return _t("Share %s people with…", s.ids.length);
    },

    get shareMoneyOn() { return this.state.shareSheet && this.state.shareSheet.partsPicked.includes("expected_pay"); },

    async saveShare() {
        const s = this.state.shareSheet;
        if (!s || s.busy) { return; }
        const dropped = s.was.filter((u) => !s.picked.includes(u));
        if (!s.picked.length && !dropped.length) {
            this.notif.add(_t("Tick at least one person to share with."), { type: "warning" });
            return;
        }
        s.busy = true;
        const before = [];
        let note = "";
        if (s.picked.length) {
            const res = await this.call4("share", {
                applicant_ids: s.ids, targets: s.picked.map((u) => ({ user_id: u })),
                parts: s.partsPicked, note: s.note,
            });
            if (!res) { s.busy = false; return; }
            before.push(...(res.before || []));
            note = res.note;
        }
        if (dropped.length) {
            const res = await this.call4("share", {
                applicant_ids: s.ids, targets: dropped.map((u) => ({ user_id: u })), parts: [],
            });
            if (res) { before.push(...(res.before || [])); note = note ? `${note} ${res.note}` : res.note; }
        }
        const ids = [...s.ids];
        this.state.shareSheet = null;
        this.clearSel();
        await this.afterShare(ids);
        this.undoableToast(note, async () => {
            const res = await this.call4("share_restore", { before });
            if (res) { await this.afterShare(ids); this.notif.add(res.note, { type: "info" }); }
        });
    },

    async unshare(row) {
        const res = await this.call4("unshare", { share_ids: [row.id] });
        if (!res) { return; }
        const ids = this.state.cand ? [this.state.cand.id] : [];
        await this.afterShare(ids);
        this.undoableToast(res.note, async () => {
            const back = await this.call4("share_restore", { before: res.before });
            if (back) { await this.afterShare(ids); }
        });
    },

    openShareSel() { this.openShare([...this.state.sel]); },

    // ====================================================== recruiter notes
    get candNotes() { return (this.state.cand && this.state.cand.notes) || { rows: [], targets: [], can_add: false }; },

    toggleNoteDraftShare(uid) {
        const ids = this.state.noteShareIds || [];
        this.state.noteShareIds = ids.includes(uid) ? ids.filter((i) => i !== uid) : [...ids, uid];
    },

    async addRecruiterNote() {
        const body = (this.state.noteDraft || "").trim();
        if (!body) { this.notif.add(_t("Write the note first."), { type: "warning" }); return; }
        const res = await this.call4("note_add", {
            applicant_id: this.state.cand.id, body, share_user_ids: this.state.noteShareIds || [],
        });
        if (!res) { return; }
        this.state.noteDraft = "";
        this.state.noteShareIds = [];
        await this.openCand(this.state.cand.id, { quiet: true });
        this.notif.add(res.note, { type: "success" });
    },

    startNoteEdit(n) { this.state.noteEdit = { note_id: n.id, body: n.body }; },

    async saveNoteEdit() {
        const f = this.state.noteEdit;
        if (!f) { return; }
        const res = await this.call4("note_edit", { note_id: f.note_id, body: f.body });
        if (!res) { return; }
        this.state.noteEdit = null;
        await this.openCand(this.state.cand.id, { quiet: true });
        this.undoableToast(res.note, async () => {
            await this.call4("note_edit", { note_id: f.note_id, body: res.old });
            await this.openCand(this.state.cand.id, { quiet: true });
        });
    },

    noteSharedWith(n, uid) { return (n.shared || []).some((u) => u.id === uid); },

    async toggleNoteShare(n, target) {
        const ids = (n.shared || []).map((u) => u.id);
        const next = ids.includes(target.id) ? ids.filter((i) => i !== target.id) : [...ids, target.id];
        const res = await this.call4("note_share", { note_id: n.id, user_ids: next });
        if (!res) { return; }
        await this.openCand(this.state.cand.id, { quiet: true });
        this.state.shareFlash = [`note-${n.id}`];
        clearTimeout(this._flashTimer);
        this._flashTimer = setTimeout(() => { this.state.shareFlash = []; }, FLASH_MS);
        this.undoableToast(res.note, async () => {
            await this.call4("note_share", { note_id: n.id, user_ids: res.before });
            await this.openCand(this.state.cand.id, { quiet: true });
        });
    },

    async deleteNote(n) {
        const res = await this.call4("note_delete", { note_id: n.id });
        if (!res) { return; }
        await this.openCand(this.state.cand.id, { quiet: true });
        this.undoableToast(res.note, async () => {
            await this.call4("note_restore", { saved: res.saved });
            await this.openCand(this.state.cand.id, { quiet: true });
        });
    },

    // ============================================================ retention
    async extendRetention() {
        const cand = this.state.cand;
        if (!cand) { return; }
        const res = await this.call4("retention_extend", { applicant_id: cand.id });
        if (res) {
            this.notif.add(res.note, { type: "success" });
            await this.openCand(cand.id, { quiet: true });
        }
    },

    retentionLine(r) {
        if (!r || !r.until) { return ""; }
        return _t("Kept until %s", this.dayLong(r.until));
    },

    dayLong(stored) {
        if (!stored) { return ""; }
        const when = new Date(`${String(stored).slice(0, 10)}T00:00:00`);
        if (isNaN(when.getTime())) { return String(stored); }
        return when.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
    },

    keepLongerLabel(r) { return _t("Keep %s more months", (r && r.months) || 12); },

    // ======================================================= role defaults
    get shareDefaults() { return (this.state.drawer && this.state.drawer.share_defaults) || null; },

    async toggleDefaultPart(key) {
        const d = this.shareDefaults;
        if (!d || !d.can_edit) { return; }
        const parts = d.parts.includes(key) ? d.parts.filter((k) => k !== key) : [...d.parts, key];
        await this.saveRoleDefaults({ parts });
    },

    async setDefaultWith(key) {
        const d = this.shareDefaults;
        if (!d || !d.can_edit || d.with === key) { return; }
        await this.saveRoleDefaults({ with: key });
    },

    async saveRoleDefaults(change) {
        const id = this.state.drawer.id;
        const res = await this.call4("role_share_defaults", { requisition_id: id, ...change });
        if (!res) { return; }
        await this.reloadRole();
        this.undoableToast(res.note, async () => {
            await this.call4("role_share_defaults", { requisition_id: id, parts: res.before.parts.split(",").filter(Boolean), with: res.before.with });
            await this.reloadRole();
        });
    },

    // ======================================================== the home tab
    setTab(tab) {
        super.setTab(tab);
        if (tab === "bank" && (!this.state.bank || !this.state.bank.loaded)) { this.loadBank(); }
    },

    blankBank() {
        return {
            loaded: false, busy: false, q: "", include_all: false, page: 0,
            picks: { skill_ids: [], country_ids: [], team_ids: [], tag_ids: [], source_ids: [] },
            rows: [], total: 0, facets: {}, skills_on: false, sel: [], options: null, error: "",
        };
    },

    async loadBank() {
        if (!this.state.bank) { this.state.bank = this.blankBank(); }
        const b = this.state.bank;
        b.busy = true;
        try {
            const res = await this.orm.call("pb.hiring", "search_bank", [{
                q: b.q, include_all: b.include_all, page: b.page, ...b.picks,
            }]);
            Object.assign(b, {
                rows: res.rows, total: res.total, facets: res.facets || {}, skills_on: res.skills_on,
                page_size: res.page_size, capped: res.capped, loaded: true, error: "",
            });
            b.sel = b.sel.filter((id) => res.rows.some((r) => r.id === id));
            if (!b.options) { b.options = await this.orm.call("pb.hiring", "bank_options", []); }
        } catch (e) {
            b.error = (e && e.data && e.data.message) || _t("The Resume bank could not be read.");
            b.loaded = true;
        } finally {
            b.busy = false;
        }
    },

    onBankQuery(ev) {
        this.state.bank.q = ev.target.value;
        this.state.bank.page = 0;
        clearTimeout(this._bankTimer);
        this._bankTimer = setTimeout(() => this.loadBank(), SEARCH_DEBOUNCE);
    },

    get bankFacets() {
        const b = this.state.bank;
        if (!b) { return []; }
        const titles = { skills: _t("Skill"), countries: _t("Country"), teams: _t("Team"), tags: _t("Tag"), sources: _t("Came from") };
        return FACETS.filter((k) => (b.facets[k] || []).length).map((k) => ({ key: k, title: titles[k], items: b.facets[k] }));
    },

    facetOn(kind, id) { return this.state.bank.picks[FACET_PICK[kind]].includes(id); },

    toggleFacet(kind, id) {
        const b = this.state.bank;
        const key = FACET_PICK[kind];
        b.picks[key] = b.picks[key].includes(id) ? b.picks[key].filter((i) => i !== id) : [...b.picks[key], id];
        b.page = 0;
        this.loadBank();
    },

    get bankAnyPick() {
        const b = this.state.bank;
        return !!(b && (b.q || Object.values(b.picks).some((v) => v.length)));
    },

    clearBank() {
        const b = this.state.bank;
        b.q = "";
        for (const k of Object.keys(b.picks)) { b.picks[k] = []; }
        b.page = 0;
        this.loadBank();
    },

    toggleIncludeAll() {
        const b = this.state.bank;
        b.include_all = !b.include_all;
        b.page = 0;
        this.loadBank();
    },

    bankPage(delta) {
        const b = this.state.bank;
        b.page = Math.max(0, b.page + delta);
        this.loadBank();
    },

    get bankShowing() {
        const b = this.state.bank;
        if (!b || !b.total) { return ""; }
        const from = b.page * (b.page_size || 40) + 1;
        const to = Math.min(b.total, from + b.rows.length - 1);
        return _t("%(from)s–%(to)s of %(total)s", { from, to, total: b.total });
    },

    isBankSel(id) { return this.state.bank.sel.includes(id); },

    toggleBankSel(id) {
        const b = this.state.bank;
        b.sel = b.sel.includes(id) ? b.sel.filter((i) => i !== id) : [...b.sel, id];
    },

    toggleBankAll() {
        const b = this.state.bank;
        b.sel = b.sel.length === b.rows.length ? [] : b.rows.map((r) => r.id);
    },

    bankExpires(row) {
        if (!row.expires_on) { return ""; }
        return this.dayLong(row.expires_on);
    },

    bankSoon(row) {
        if (!row.expires_on) { return false; }
        const days = (new Date(`${row.expires_on}T00:00:00`) - new Date()) / 86400000;
        return days < 31;
    },

    // ---------------------------------------------------- add to a role
    startBankAdd(ids) {
        const b = this.state.bank;
        this.state.bankAdd = { ids: [...ids], requisition_id: "", q: "", busy: false, roles: (b.options && b.options.roles) || [] };
    },

    get bankAddRoles() {
        const f = this.state.bankAdd;
        if (!f) { return []; }
        const q = (f.q || "").trim().toLowerCase();
        return f.roles.filter((r) => !q || `${r.title} ${r.country} ${r.department}`.toLowerCase().includes(q)).slice(0, 40);
    },

    async saveBankAdd() {
        const f = this.state.bankAdd;
        if (!f || !f.requisition_id || f.busy) { return; }
        f.busy = true;
        const res = await this.call4("bank_add_to_role", { applicant_ids: f.ids, requisition_id: Number(f.requisition_id) });
        f.busy = false;
        if (!res) { return; }
        this.state.bankAdd = null;
        this.state.bank.sel = [];
        this.notif.add(res.note, {
            type: res.added && res.added.length ? "success" : "warning",
            buttons: res.added && res.added.length ? [{
                name: _t("Open the role"), primary: true,
                onClick: () => this.openRole(res.requisition_id, { tab: "board" }),
            }] : [],
        });
        await this.loadBank();
    },

    // ------------------------------------------------------------- tags
    startBankTag(ids) {
        const b = this.state.bank;
        this.state.bankTag = { ids: [...ids], tag_id: "", new_tag: "", busy: false, tags: (b.options && b.options.tags) || [] };
    },

    async saveBankTag() {
        const f = this.state.bankTag;
        if (!f || f.busy) { return; }
        if (!f.tag_id && !f.new_tag.trim()) { this.notif.add(_t("Pick a tag, or type a new one."), { type: "warning" }); return; }
        f.busy = true;
        const payload = { applicant_ids: f.ids, tag_ids: f.tag_id ? [Number(f.tag_id)] : [], new_tag: f.new_tag, op: "add" };
        const res = await this.call4("bank_tag", payload);
        f.busy = false;
        if (!res) { return; }
        this.state.bankTag = null;
        this.state.bank.options = null;
        await this.loadBank();
        this.undoableToast(res.note, async () => {
            await this.call4("bank_tag", { applicant_ids: f.ids, tag_ids: res.tag_ids, op: "remove" });
            await this.loadBank();
        });
    },

    async removeBankTag(row, tag) {
        const res = await this.call4("bank_tag", { applicant_ids: [row.id], tag_ids: [tag.id], op: "remove" });
        if (!res) { return; }
        await this.loadBank();
        this.undoableToast(res.note, async () => {
            await this.call4("bank_tag", { applicant_ids: [row.id], tag_ids: [tag.id], op: "add" });
            await this.loadBank();
        });
    },

    // ------------------------------------------------------ keyboard
    onKey(ev) {
        if (this.state.view === "home" && this.state.tab === "bank" && ev.key === "Escape") {
            if (this.state.bankAdd) { this.state.bankAdd = null; ev.stopPropagation(); return; }
            if (this.state.bankTag) { this.state.bankTag = null; ev.stopPropagation(); return; }
            if (this.state.bank && this.state.bank.sel.length) { this.state.bank.sel = []; ev.stopPropagation(); return; }
        }
        if (ev.key === "Escape" && this.state.shareSheet) { this.state.shareSheet = null; ev.stopPropagation(); ev.preventDefault(); return; }
        if (ev.key === "Escape" && this.state.noteEdit) { this.state.noteEdit = null; ev.stopPropagation(); ev.preventDefault(); return; }
        const t = ev.target;
        const typing = t && (t.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName));
        if (!typing && !this.anyDialog && this.state.cand && this.state.cand.share && (ev.key === "s" || ev.key === "S")
                && !ev.metaKey && !ev.ctrlKey && !ev.altKey) {
            ev.preventDefault();
            this.openShare([this.state.cand.id]);
            return;
        }
        if (!typing && !this.anyDialog && this.state.view === "role" && this.state.sel.length && (ev.key === "s" || ev.key === "S")
                && !ev.metaKey && !ev.ctrlKey && !ev.altKey && this.state.canRecruit) {
            ev.preventDefault();
            this.openShareSel();
            return;
        }
        return super.onKey(ev);
    },

    get anyDialog() {
        const s = this.state;
        return super.anyDialog || !!(s.shareSheet || s.noteEdit || s.bankAdd || s.bankTag);
    },

    // ------------------------------------------------- words for the drawer
    partWord(key) {
        return {
            profile: _t("Profile"), cv: _t("CV"), portfolio: _t("Portfolio"), assignment: _t("Assignment"),
            attachments: _t("Other files"), answers: _t("Answers"), scorecards: _t("Scorecards"),
            expected_pay: _t("Expected pay"),
        }[key] || key;
    },

    sharedSince(row) { return _t("since %s", this.dayShort(row.on)); },

    candLockTitle(cand) {
        if (cand.can_recruit) {
            return cand.share && !cand.share.private ? _t("Shared") : _t("Private to hiring");
        }
        return cand.locked ? _t("Not shared with you") : _t("Shared with you");
    },
});
