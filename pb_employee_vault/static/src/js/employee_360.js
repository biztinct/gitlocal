/** @odoo-module **/
/**
 * Employee 360 drawer — a bespoke slide-in over the People roster with three
 * tabs (Profile · Documents · Timeline). It registers into the soft
 * "pb_people_drawer" registry so the People cockpit mounts it ONLY when this
 * module is installed; People stays fully installable without the vault.
 *
 * RPC facade: pb.people (get_employee_360 / vault_* / get_timeline_page). Teal
 * .ppl theme. Lucide icons only. Wage VALUES are masked server-side for
 * non-payroll-managers — the client never sees a number it may not show.
 */
import { Component, useState, onWillStart, onMounted, useExternalListener } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic, CAT_ICON } from "@pb_employee_vault/js/pev_icons";

const MODEL = "pb.people";
const STATE_CLS = { open: "ok", close: "warn", draft: "info", cancel: "muted", none: "muted", expired: "warn", running: "ok" };
const KIND_TONE = { employee: "indigo", contract: "teal", bank: "cyan", approval: "green" };

export class Employee360Drawer extends Component {
    static template = "pb_employee_vault.Employee360Drawer";
    static props = {
        empId: { type: [Number, String] },
        onClose: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.state = useState({
            loaded: false, shown: false, busy: false,
            tab: "profile", d: null,
            tlOffset: 0, uploadCatId: null, uploading: false,
        });
        onWillStart(() => this.load());
        onMounted(() => { this.state.shown = true; });
        // ESC closes (capture phase — the roster does not consume Escape, but
        // capture is the safe C3 pattern for a non-focus-stealing overlay).
        useExternalListener(window, "keydown", (ev) => this.onKey(ev), { capture: true });
    }

    ic(n, s = 16) { return ic(n, s); }
    catIcon(code) { return ic(CAT_ICON[code] || "file", 18); }
    get d() { return this.state.d || {}; }
    get profile() { return (this.state.d && this.state.d.profile) || {}; }
    stateCls(s) { return STATE_CLS[s] || "muted"; }
    kindTone(k) { return KIND_TONE[k] || "indigo"; }

    async load() {
        try {
            this.state.d = await this.orm.call(MODEL, "get_employee_360", [Number(this.props.empId)]);
        } catch (e) {
            this.state.d = { error: (e && e.message && e.message.data && e.message.data.message) || "Could not load this employee." };
        } finally {
            this.state.loaded = true;
        }
    }

    // ---- chrome ----
    setTab(t) { this.state.tab = t; }
    onKey(ev) { if (ev.key === "Escape") { this.close(); } }
    close() {
        this.state.shown = false;
        // let the slide-out play before the parent unmounts us
        const done = this.props.onClose || (() => { });
        setTimeout(done, 180);
    }

    // ---- formatting ----
    money(n) {
        const cur = (this.profile.currency) || "₫";
        if (n === null || n === undefined || n === "") return "—";
        return cur + Math.round(n).toLocaleString("en-US");
    }
    initials(name) {
        const parts = (name || "").replace("-", " ").split(" ").filter(Boolean);
        return ((parts[0] ? parts[0][0] : "?") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
    }
    expiryCls(doc) {
        const s = doc.expiry_state;
        if (s === "expired") return "rose";
        if (s === "soon") return "amber";
        if (s === "valid") return "green";
        return "muted";
    }
    expiryLabel(doc) {
        if (!doc.expiry_date) return _t("No expiry");
        const d = doc.days_to_expiry;
        if (d === null || d === undefined) return doc.expiry_date;
        if (d < 0) return _t("Expired %(days)s days ago", { days: Math.abs(d) });
        if (d === 0) return _t("Expires today");
        return _t("Expires in %(days)s days", { days: d });
    }
    docsByCategory() {
        const groups = {};
        for (const c of (this.d.categories || [])) groups[c.id] = { cat: c, docs: [] };
        for (const doc of (this.d.documents || [])) {
            if (!groups[doc.category_id]) groups[doc.category_id] = { cat: { id: doc.category_id, name: doc.category, code: doc.category_code, requires_expiry: doc.requires_expiry }, docs: [] };
            groups[doc.category_id].docs.push(doc);
        }
        return Object.values(groups);
    }

    // ---- documents: upload / verify / delete ----
    triggerPick(catId) {
        this.state.uploadCatId = catId;
        const input = document.getElementById("pev-file-" + catId);
        if (input) { input.value = ""; input.click(); }
    }
    onFilePicked(catId, ev) {
        const file = ev.target.files && ev.target.files[0];
        if (file) { this.uploadFile(catId, file); }
    }
    onDrop(catId, ev) {
        ev.preventDefault();
        const file = ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files[0];
        if (file) { this.uploadFile(catId, file); }
    }
    onDragOver(ev) { ev.preventDefault(); }

    async uploadFile(catId, file) {
        const OK = ["image/png", "image/jpeg", "application/pdf"];
        if (!OK.includes(file.type)) {
            this.notif.add(_t("Only JPG, PNG or PDF documents are accepted."), { type: "danger" });
            return;
        }
        this.state.uploading = true;
        try {
            const dataUrl = await this._readAsDataURL(file);
            const b64 = String(dataUrl).split(",")[1] || "";
            const payload = { name: file.name, title: file.name.replace(/\.[^.]+$/, ""), mime: file.type, data: b64 };
            this.state.d = await this.orm.call(MODEL, "vault_upload", [Number(this.props.empId), catId, payload]);
            this.notif.add(_t("Document uploaded."), { type: "success" });
        } catch (e) {
            this.notif.add(this._err(e, _t("Upload failed.")), { type: "danger" });
        } finally {
            this.state.uploading = false;
        }
    }
    _readAsDataURL(file) {
        return new Promise((resolve, reject) => {
            const r = new FileReader();
            r.onload = () => resolve(r.result);
            r.onerror = () => reject(r.error);
            r.readAsDataURL(file);
        });
    }

    async verify(doc, flag) {
        this.state.busy = true;
        try {
            this.state.d = await this.orm.call(MODEL, "vault_verify", [doc.id, flag]);
        } catch (e) {
            this.notif.add(this._err(e, _t("Could not update verification.")), { type: "danger" });
        } finally { this.state.busy = false; }
    }
    async del(doc) {
        this.state.busy = true;
        try {
            this.state.d = await this.orm.call(MODEL, "vault_delete", [doc.id]);
            this.notif.add(_t("Document removed."), { type: "success" });
        } catch (e) {
            this.notif.add(this._err(e, _t("Could not delete this document.")), { type: "danger" });
        } finally { this.state.busy = false; }
    }

    // ---- timeline load-more ----
    async loadMore() {
        this.state.busy = true;
        try {
            const res = await this.orm.call(MODEL, "get_timeline_page", [Number(this.props.empId), (this.d.timeline || []).length]);
            const merged = (this.d.timeline || []).concat(res.items || []);
            this.state.d = Object.assign({}, this.state.d, { timeline: merged, timeline_shown: res.shown, timeline_total: res.total });
        } catch (e) {
            this.notif.add(this._err(e, _t("Could not load more history.")), { type: "danger" });
        } finally { this.state.busy = false; }
    }
    get hasMoreTimeline() {
        return (this.d.timeline || []).length < (this.d.timeline_total || 0);
    }

    // month separators for the timeline
    timelineRows() {
        const out = [];
        let lastMonth = null;
        for (const it of (this.d.timeline || [])) {
            const m = (it.stamp || "").slice(0, 7);
            if (m && m !== lastMonth) { out.push({ sep: true, key: "sep-" + m, label: this._monthLabel(m) }); lastMonth = m; }
            out.push(Object.assign({ sep: false, key: "it-" + out.length }, it));
        }
        return out;
    }
    _monthLabel(m) {
        const [y, mo] = m.split("-");
        const names = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        return (names[parseInt(mo, 10)] || "") + " " + y;
    }
    relDate(stamp) {
        if (!stamp) return "";
        const d = new Date(stamp.replace(" ", "T") + "Z");
        const days = Math.floor((Date.now() - d.getTime()) / 86400000);
        if (days <= 0) return "today";
        if (days === 1) return "yesterday";
        if (days < 30) return days + "d ago";
        if (days < 365) return Math.floor(days / 30) + "mo ago";
        return Math.floor(days / 365) + "y ago";
    }

    _err(e, fallback) {
        return (e && e.message && e.message.data && e.message.data.message) || (e && e.message) || fallback;
    }
}

registry.category("pb_people_drawer").add("employee_360", Employee360Drawer);
