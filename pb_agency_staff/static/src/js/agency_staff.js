/** @odoo-module **/
/**
 * `pb_agency_staff` — People › Agency staff: people an agency supplies, kept
 * apart from employees (owner ruling J5). Quiet glance, filter panel, and a
 * side drawer to add or change one person and keep their papers.
 *
 * R1 — no `t-as` named lt/gt/lte/gte/and/or/not/in (UPDATES G60).
 * R2 — icons are the filter kit's CACHED markup (`pbfIcon`).
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { useFilterKit, pbfIcon } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";

const MODEL = "pb.agency.board";
const PAGE = 40;
const GLANCE_FILTERS = {
    on_site: { where: ["on_site"] },
    upcoming: { where: ["upcoming"] },
    ending: { where: ["ending"] },
    ended: { where: ["ended"] },
};

function errText(e, fallback) {
    const data = (e && e.data) || (e && e.message && e.message.data);
    return (data && data.message) || fallback;
}

function blank(companyId) {
    return { id: 0, name: "", job_title: "", vendor_id: 0, department_id: 0, work_location_id: 0,
             manager_id: 0, manager: "", company_id: companyId || 0, date_start: "", date_end: "",
             phone: "", email: "", notes: "", files: [] };
}

export class PbAgencyStaff extends Component {
    static template = "pb_agency_staff.PbAgencyStaff";
    static components = { PbFilterLayout };
    static props = ["*"];

    get searchLabel() { return _t("Find by name, role or agency…"); }

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.state = useState({
            loaded: false, allowed: true, why: "", kpis: {}, total: 0, canDelete: false,
            rows: [], listTotal: 0, listLoaded: false, listError: false, loadingMore: false,
            drawer: null, options: null,
        });
        this.kit = useFilterKit({ model: MODEL, noun: _t("agency staff"), onChange: () => this.loadPage() });
        onWillStart(async () => { await this.load(); if (!this.state.allowed) { this.state.listLoaded = true; } });
    }

    icon(name, size = 16) { return pbfIcon(name, size); }
    fmtInt(n) { return Number(n || 0).toLocaleString(); }

    async load() {
        try {
            const d = await this.orm.call(MODEL, "get_board", []);
            Object.assign(this.state, { allowed: d.allowed !== false, why: d.why || "", kpis: d.kpis || {},
                                        total: d.total || 0, canDelete: !!d.can_delete });
        } catch (e) {
            this.state.allowed = false;
            this.state.why = _t("The list could not be read just now.");
        } finally {
            this.state.loaded = true;
        }
    }

    async loadPage({ more = false } = {}) {
        if (this.kit.refusal) { this.state.listLoaded = true; return; }
        const q = this.kit.query;
        const offset = more ? this.state.rows.length : 0;
        if (more) { this.state.loadingMore = true; }
        try {
            const d = await this.orm.call(MODEL, "get_page", [], this.kit.kw({
                filters: q.filters, search: q.search, sort: q.sort, offset, limit: PAGE }));
            if (!this.kit.isCurrent(q.seq)) { return; }
            this.state.rows = more ? [...this.state.rows, ...d.rows] : d.rows;
            this.state.listTotal = d.total;
            this.state.listLoaded = true;
            this.state.listError = false;
        } catch (e) {
            if (!this.kit.isCurrent(q.seq)) { return; }
            if (!more) { this.state.listError = true; this.state.listLoaded = true; }
        } finally {
            this.state.loadingMore = false;
        }
    }
    loadMore() { if (!this.state.loadingMore) { this.loadPage({ more: true }); } }
    retry() { this.state.listError = false; this.state.listLoaded = false; this.kit.refresh(); }
    get hasMore() { return this.state.rows.length < this.state.listTotal; }
    get nextPage() { return Math.min(PAGE, this.state.listTotal - this.state.rows.length); }
    async refresh() { await Promise.all([this.load(), this.kit.refresh()]); }

    get glance() {
        const k = this.state.kpis || {};
        const tone = (v, t) => (v ? t : "");
        const pick = (id) => () => this.kit.toggleFilters(GLANCE_FILTERS[id]);
        return [
            { key: "on_site", n: k.on_site || 0, label: _t("on site"), tone: "", run: pick("on_site") },
            { key: "upcoming", n: k.upcoming || 0, label: _t("starting later"), tone: tone(k.upcoming, "blue"), run: pick("upcoming") },
            { key: "ending", n: k.ending || 0, label: _t("ending in 30 days"), tone: tone(k.ending, "amber"), run: pick("ending") },
            { key: "ended", n: k.ended || 0, label: _t("ended"), tone: "", run: pick("ended") },
        ];
    }
    get glanceOn() {
        if (!this.kit.loaded) { return ""; }
        for (const [key, f] of Object.entries(GLANCE_FILTERS)) {
            if (this.kit.isExactly(f)) { return key; }
        }
        return "";
    }

    // ------------------------------------------------------------ the drawer
    async ensureOptions() {
        if (!this.state.options) {
            this.state.options = await this.orm.call(MODEL, "options", []);
        }
        return this.state.options;
    }
    async openNew() {
        const o = await this.ensureOptions();
        this.state.drawer = { w: blank(o.company_id), busy: false, mgr: { term: "", rows: [], open: false } };
    }
    async openWorker(id) {
        await this.ensureOptions();
        try {
            const w = await this.orm.call(MODEL, "get_worker", [id]);
            this.state.drawer = { w, busy: false, mgr: { term: w.manager || "", rows: [], open: false } };
        } catch (e) {
            this.notif.add(errText(e, _t("This person could not be opened.")), { type: "danger" });
        }
    }
    close() { this.state.drawer = null; }
    onField(key, ev, number = false) {
        let v = ev.target.value;
        if (number) { v = parseInt(v, 10) || 0; }
        this.state.drawer.w[key] = v;
    }
    onMgr(ev) {
        const dr = this.state.drawer;
        dr.mgr.term = ev.target.value;
        dr.mgr.open = true;
        if (!dr.mgr.term) { dr.w.manager_id = 0; }
        clearTimeout(this._t);
        this._t = setTimeout(async () => {
            try { dr.mgr.rows = await this.orm.call(MODEL, "managers", [dr.mgr.term, dr.w.company_id]); } catch { dr.mgr.rows = []; }
        }, 250);
    }
    pickMgr(m) {
        const dr = this.state.drawer;
        dr.w.manager_id = m.id; dr.mgr.term = m.label; dr.mgr.open = false;
    }
    blurMgr() { setTimeout(() => { if (this.state.drawer) { this.state.drawer.mgr.open = false; } }, 150); }

    async save() {
        const dr = this.state.drawer;
        if (!dr || dr.busy) { return; }
        dr.busy = true;
        const w = dr.w;
        try {
            const res = await this.orm.call(MODEL, "save_worker", [{
                id: w.id, name: w.name, job_title: w.job_title, vendor_id: w.vendor_id,
                department_id: w.department_id, work_location_id: w.work_location_id,
                manager_id: w.manager_id, company_id: w.company_id,
                date_start: w.date_start, date_end: w.date_end,
                phone: w.phone, email: w.email, notes: w.notes }]);
            this.notif.add(res.msg, { type: "success" });
            if (!w.id) { await this.openWorker(res.id); } else { dr.busy = false; }
            await this.refresh();
        } catch (e) {
            this.notif.add(errText(e, _t("This could not be saved.")), { type: "danger" });
            if (this.state.drawer) { this.state.drawer.busy = false; }
        }
    }
    async endToday() {
        const dr = this.state.drawer;
        if (!dr || !dr.w.id) { return; }
        try {
            const res = await this.orm.call(MODEL, "end_worker", [dr.w.id]);
            this.notif.add(res.msg, { type: "success" });
            await this.openWorker(dr.w.id);
            await this.refresh();
        } catch (e) {
            this.notif.add(errText(e, _t("That could not be done.")), { type: "danger" });
        }
    }
    async remove() {
        const dr = this.state.drawer;
        if (!dr || !dr.w.id) { return; }
        try {
            const res = await this.orm.call(MODEL, "delete_worker", [dr.w.id]);
            this.notif.add(res.msg, { type: "success" });
            this.state.drawer = null;
            await this.refresh();
        } catch (e) {
            this.notif.add(errText(e, _t("That could not be done.")), { type: "danger" });
        }
    }
    async onFile(ev) {
        const dr = this.state.drawer;
        const file = ev.target.files && ev.target.files[0];
        if (!dr || !file || !dr.w.id) { return; }
        const data = await new Promise((resolve, reject) => {
            const r = new FileReader();
            r.onload = () => resolve(String(r.result).split(",")[1] || "");
            r.onerror = reject;
            r.readAsDataURL(file);
        });
        try {
            dr.w = await this.orm.call(MODEL, "add_file", [dr.w.id, file.name, file.type, data]);
        } catch (e) {
            this.notif.add(errText(e, _t("The file could not be added.")), { type: "danger" });
        }
        ev.target.value = "";
    }
    async removeFile(fileId) {
        const dr = this.state.drawer;
        try {
            dr.w = await this.orm.call(MODEL, "remove_file", [dr.w.id, fileId]);
        } catch (e) {
            this.notif.add(errText(e, _t("The file could not be removed.")), { type: "danger" });
        }
    }
}

registry.category("actions").add("pb_agency_staff", PbAgencyStaff);
