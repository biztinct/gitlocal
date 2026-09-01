/** @odoo-module **/
/**
 * `pb_vendors_board` — the Vendors panel behind the Settings cog.
 *
 * THE HERO IS THE RENEWAL RUNWAY. Every card carries one bar: how much of the
 * agreement's term has been used up, with the point where the renewal
 * conversation was meant to start marked on it. A fill past that notch is a
 * conversation somebody is late for, and it reads in about a second — the same
 * one-comparison idea the budget heat view is built on.
 *
 * COLOUR IS NEVER THE MESSAGE. Every card carries the number of days and a word
 * — "Running", "Ending soon", "Ended", "Replaced by a newer one" — so the board
 * reads identically to somebody who cannot tell the amber from the rose.
 *
 * THE MOTION IS A CSS CUSTOM PROPERTY AND IT IS OPTIONAL. Cards rise on a
 * stagger driven by `--pbva-i`, set per card from the loop index; the whole
 * animation, the transform and the opacity all live inside a
 * `@media (prefers-reduced-motion: no-preference)` block in the stylesheet, so
 * somebody who has asked their machine for less movement gets the finished
 * board on the first frame with nothing to recover from (R85).
 *
 * R1 — no `t-as` variable is named lt / gt / lte / gte / and / or / not / in.
 * R2 — every sentence is ONE expression; JavaScript has no implicit string
 * concatenation and a Python habit here kills the entire asset bundle.
 * R34 — a sentence split across several `t-esc` nodes loses its spaces, so
 * every sentence on this board is built in one expression.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubBackChip, hubBack } from "@pb_hub/js/hub_nav";

const BLANK_VENDOR = {
    id: 0, name: "", vendor_type: "services", contact_name: "",
    contact_email: "", contact_phone: "", department_id: 0, department: "",
    responsible_user_id: 0, responsible: "", country_id: 0, notes: "",
};

const BLANK_AGREEMENT = {
    id: 0, name: "", date_start: "", date_end: "", renewal_date: "",
    value: "", note: "",
};

export class PbVendorsBoard extends Component {
    static template = "pb_vendor_access.PbVendorsBoard";
    static components = { HubBackChip };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");

        // Read ONCE, from props, never written back (HubShell's rule).
        this.back = hubBack(this.props);

        this.state = useState({
            loaded: false,
            failed: "",
            board: null,

            // filters
            type: "",
            department_id: 0,
            agreementState: "",
            search: "",

            // the drawer
            open: 0,
            drawer: null,
            drawerBusy: false,

            // dialogs
            editing: false,
            vendor: { ...BLANK_VENDOR },
            people: [],
            departments: [],

            agreeing: false,
            agreement: { ...BLANK_AGREEMENT },

            renewing: 0,
            renewal: { ...BLANK_AGREEMENT },

            busy: false,
        });

        onWillStart(async () => { await this.load(); });
    }

    ic(n, s = 16) { return ic(n, s); }

    // ------------------------------------------------------------- reading
    async load() {
        try {
            this.state.board = await this.orm.call("pb.vendors", "get_board", [
                this.state.type || null,
                this.state.department_id || null,
                this.state.agreementState || null,
                this.state.search || null,
            ]);
            this.state.failed = "";
        } catch (e) {
            // Reported, never swallowed into a decoration: a board that could
            // not be read says so, and never shows an empty list as though it
            // were the answer.
            this.state.board = null;
            this.state.failed = this._msg(
                e, _t("The vendor register could not be read."));
        } finally {
            this.state.loaded = true;
        }
    }

    async reload() {
        this.state.loaded = false;
        await this.load();
        if (this.state.open) { await this.refreshDrawer(); }
    }

    get board() { return this.state.board || {}; }
    get rows() { return this.board.rows || []; }
    get kpis() { return this.board.kpis || {}; }
    get facets() { return this.board.facets || {}; }
    get canEdit() { return Boolean(this.board.can_edit); }

    // -------------------------------------------------------------- filters
    async setType(key) {
        this.state.type = this.state.type === key ? "" : key;
        await this.reload();
    }

    async setState(key) {
        this.state.agreementState = this.state.agreementState === key
            ? "" : key;
        await this.reload();
    }

    async setDepartment(id) {
        this.state.department_id = this.state.department_id === id ? 0 : id;
        await this.reload();
    }

    async onSearch(ev) {
        this.state.search = ev.target.value;
        await this.load();
    }

    async clearFilters() {
        this.state.type = "";
        this.state.department_id = 0;
        this.state.agreementState = "";
        this.state.search = "";
        await this.reload();
    }

    get filtered() {
        return Boolean(this.state.type || this.state.department_id
                       || this.state.agreementState || this.state.search);
    }

    // -------------------------------------------------------------- the bar
    /**
     * How far through its term an agreement is, 0-100.
     *
     * NOT how many days are left: a three-year agreement with sixty days on it
     * and a sixty-day agreement with sixty days on it are the same number of
     * days and completely different situations.
     */
    runway(a) {
        const start = this._date(a.date_start);
        const end = this._date(a.date_end);
        if (!start || !end || end <= start) { return 100; }
        const now = Date.now();
        const pct = (now - start) / (end - start) * 100;
        return Math.max(0, Math.min(100, Math.round(pct)));
    }

    /** Where on that bar the renewal conversation was meant to start. */
    notch(a) {
        const start = this._date(a.date_start);
        const end = this._date(a.date_end);
        const talk = this._date(a.renewal_date);
        if (!start || !end || !talk || end <= start) { return 100; }
        const pct = (talk - start) / (end - start) * 100;
        return Math.max(0, Math.min(100, Math.round(pct)));
    }

    _date(s) {
        if (!s) { return 0; }
        const d = new Date(`${s}T00:00:00`);
        return isNaN(d.getTime()) ? 0 : d.getTime();
    }

    /** A date a person reads, never the raw ISO string (R108's shape). */
    day(s) {
        if (!s) { return ""; }
        const d = new Date(`${s}T00:00:00`);
        if (isNaN(d.getTime())) { return s; }
        return d.toLocaleDateString(undefined, {
            day: "numeric", month: "short", year: "numeric",
        });
    }

    /** ONE expression per sentence, so the spaces survive (R34). */
    daysLine(a) {
        if (a.state === "renewed") {
            return _t("Replaced by a newer agreement.");
        }
        if (a.days_left < 0) {
            return _t("Ran out %s days ago.", Math.abs(a.days_left));
        }
        if (a.days_left === 0) { return _t("Ends today."); }
        if (a.days_left === 1) { return _t("Ends tomorrow."); }
        return _t("%s days left.", a.days_left);
    }

    money(v, cur) {
        const n = Math.round(Number(v) || 0);
        if (!n) { return ""; }
        return `${n.toLocaleString()} ${cur || ""}`.trim();
    }

    // -------------------------------------------------------------- drawer
    async openVendor(row) {
        if (this.state.open === row.id) { this.closeDrawer(); return; }
        this.state.open = row.id;
        this.state.drawer = null;
        this.state.drawerBusy = true;
        try {
            this.state.drawer = await this.orm.call(
                "pb.vendors", "get_vendor", [row.id]);
        } catch (e) {
            this.notif.add(this._msg(e, _t("That vendor could not be opened.")),
                           { type: "danger" });
            this.state.open = 0;
        } finally {
            this.state.drawerBusy = false;
        }
    }

    async refreshDrawer() {
        if (!this.state.open) { return; }
        try {
            this.state.drawer = await this.orm.call(
                "pb.vendors", "get_vendor", [this.state.open]);
        } catch (e) {
            this.state.drawer = null;
        }
    }

    closeDrawer() {
        this.state.open = 0;
        this.state.drawer = null;
    }

    // ------------------------------------------------------- the vendor form
    openAdd() {
        this.state.vendor = { ...BLANK_VENDOR };
        this.state.people = [];
        this.state.departments = [];
        this.state.editing = true;
    }

    openEdit() {
        const d = this.state.drawer;
        if (!d) { return; }
        const v = d.vendor;
        this.state.vendor = {
            id: v.id, name: v.name, vendor_type: v.type,
            contact_name: v.contact_name, contact_email: v.contact_email,
            contact_phone: v.contact_phone,
            department_id: v.department_id, department: v.department,
            responsible_user_id: v.responsible_id, responsible: v.responsible,
            country_id: 0, notes: d.notes || "",
        };
        this.state.people = [];
        this.state.departments = [];
        this.state.editing = true;
    }

    closeEdit() { this.state.editing = false; }

    onVendorField(field, ev) {
        this.state.vendor[field] = ev.target.value;
    }

    setVendorType(key) { this.state.vendor.vendor_type = key; }

    async onOwnerSearch(ev) {
        const term = ev.target.value;
        this.state.vendor.responsible = term;
        this.state.vendor.responsible_user_id = 0;
        if (!term || term.length < 2) { this.state.people = []; return; }
        try {
            this.state.people = await this.orm.call(
                "pb.vendors", "user_options", [term]);
        } catch (e) {
            this.state.people = [];
        }
    }

    pickOwner(person) {
        this.state.vendor.responsible_user_id = person.id;
        this.state.vendor.responsible = person.name;
        this.state.people = [];
    }

    async onDeptSearch(ev) {
        const term = ev.target.value;
        this.state.vendor.department = term;
        this.state.vendor.department_id = 0;
        if (!term || term.length < 2) { this.state.departments = []; return; }
        try {
            this.state.departments = await this.orm.call(
                "pb.vendors", "department_options", [term]);
        } catch (e) {
            this.state.departments = [];
        }
    }

    pickDept(dept) {
        this.state.vendor.department_id = dept.id;
        this.state.vendor.department = dept.name;
        this.state.departments = [];
    }

    async saveVendor() {
        const v = this.state.vendor;
        if (!(v.name || "").trim()) {
            this.notif.add(_t("Say who they are."), { type: "warning" });
            return;
        }
        this.state.busy = true;
        try {
            const res = await this.orm.call("pb.vendors", "save_vendor", [{
                id: v.id, name: v.name, vendor_type: v.vendor_type,
                contact_name: v.contact_name, contact_email: v.contact_email,
                contact_phone: v.contact_phone,
                department_id: v.department_id,
                responsible_user_id: v.responsible_user_id || undefined,
                notes: v.notes,
            }]);
            this.state.editing = false;
            this.notif.add(res.message, { type: "success" });
            this.state.open = res.id;
            await this.reload();
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be saved.")),
                           { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // ---------------------------------------------------- the agreement form
    openAgreement() {
        const today = new Date().toISOString().slice(0, 10);
        this.state.agreement = { ...BLANK_AGREEMENT, date_start: today };
        this.state.agreeing = true;
    }

    closeAgreement() { this.state.agreeing = false; }

    onAgreementField(field, ev) {
        this.state.agreement[field] = ev.target.value;
    }

    async saveAgreement() {
        const a = this.state.agreement;
        if (!(a.name || "").trim()) {
            this.notif.add(_t("Say what the agreement covers."),
                           { type: "warning" });
            return;
        }
        if (!a.date_end) {
            this.notif.add(
                _t("Say when it ends — that is the date this whole screen is "
                   + "about."),
                { type: "warning" });
            return;
        }
        this.state.busy = true;
        try {
            const res = await this.orm.call("pb.vendors", "save_agreement", [{
                id: a.id, vendor_id: this.state.open, name: a.name,
                date_start: a.date_start, date_end: a.date_end,
                renewal_date: a.renewal_date || false,
                value: Number(a.value) || 0, note: a.note,
            }]);
            this.state.agreeing = false;
            this.notif.add(res.message, { type: "success" });
            await this.reload();
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be saved.")),
                           { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // ------------------------------------------------------------ the renewal
    openRenew(a) {
        const start = a.date_end
            ? new Date(new Date(`${a.date_end}T00:00:00`).getTime() + 86400000)
                .toISOString().slice(0, 10)
            : "";
        const span = (this._date(a.date_end) - this._date(a.date_start))
            || (365 * 86400000);
        const end = start
            ? new Date(new Date(`${start}T00:00:00`).getTime() + span)
                .toISOString().slice(0, 10)
            : "";
        this.state.renewal = {
            id: a.id, name: a.name, date_start: start, date_end: end,
            renewal_date: "", value: a.value || "", note: "",
        };
        this.state.renewing = a.id;
    }

    closeRenew() { this.state.renewing = 0; }

    onRenewalField(field, ev) {
        this.state.renewal[field] = ev.target.value;
    }

    async saveRenewal() {
        const r = this.state.renewal;
        this.state.busy = true;
        try {
            const res = await this.orm.call("pb.vendors", "renew_agreement", [
                this.state.renewing, {
                    name: r.name, date_start: r.date_start,
                    date_end: r.date_end, value: Number(r.value) || 0,
                    note: r.note,
                },
            ]);
            this.state.renewing = 0;
            this.notif.add(res.message, { type: "success", sticky: true });
            await this.reload();
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be renewed.")),
                           { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // -------------------------------------------------------------- the files
    onFile(agreementId, ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file) { return; }
        const reader = new FileReader();
        reader.onload = async () => {
            const b64 = String(reader.result).split(",")[1] || "";
            try {
                const res = await this.orm.call("pb.vendors", "attach", [
                    agreementId, file.name, b64,
                ]);
                this.notif.add(res.message, { type: "success" });
                await this.refreshDrawer();
            } catch (e) {
                this.notif.add(
                    this._msg(e, _t("That file could not be filed.")),
                    { type: "danger" });
            }
        };
        reader.readAsDataURL(file);
        ev.target.value = "";
    }

    async detach(agreementId, attachmentId) {
        try {
            const res = await this.orm.call("pb.vendors", "detach", [
                agreementId, attachmentId,
            ]);
            this.notif.add(res.message, { type: "success" });
            await this.refreshDrawer();
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be taken off.")),
                           { type: "danger" });
        }
    }

    // --------------------------------------------------------------- actions
    async runAlerts() {
        this.state.busy = true;
        try {
            const res = await this.orm.call("pb.vendors", "run_alerts", []);
            this.notif.add(res.message, { type: "success", sticky: true });
            await this.reload();
        } catch (e) {
            this.notif.add(
                this._msg(e, _t("The agreements could not be checked.")),
                { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async exportFile() {
        this.state.busy = true;
        try {
            const res = await this.orm.call("pb.vendors", "export_vendors", []);
            this.download(res);
            this.notif.add(_t("The spreadsheet has been downloaded."),
                           { type: "success" });
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be built.")),
                           { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    /** base64 to a saved file, without ever leaving the page. */
    download(res) {
        const binary = window.atob(res.file_b64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i);
        }
        const blob = new Blob([bytes], { type: res.mimetype });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = res.filename;
        link.click();
        URL.revokeObjectURL(url);
    }

    openList() {
        this.action.doAction("pb_vendor_access.action_pb_vendor");
    }

    // ----------------------------------------------------------------- errors
    _msg(e, fallback) {
        if (e && e.message && e.message.data && e.message.data.message) {
            return e.message.data.message;
        }
        if (e && e.data && e.data.message) { return e.data.message; }
        return fallback;
    }
}

registry.category("actions").add("pb_vendors_board", PbVendorsBoard);
