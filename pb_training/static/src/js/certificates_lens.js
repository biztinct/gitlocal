/** @odoo-module **/
/**
 * Learning › CERTIFICATES (LEARNING L1) — the register.
 *
 * HERO MOMENT: one sentence over six tiles — "214 certificates. 12 expire
 * within 30 days, 3 have expired." Every tile is a filter (press again to
 * clear), quiet board: grey at zero, amber for "expire within", rose for
 * expired, green for in date.
 *
 * Under it: search (accents do not matter — the server folds them),
 * department and job, then the table with a state chip and a "what happens
 * next" line on every row, and three row actions: Assign the refresher,
 * Verify, Download (plus the person's learning record). "Add a certificate"
 * opens a drawer: person, name, kind, issued by, number, dates, file.
 *
 * Reads `pb.training.certificates_board` (gated like the board — a reader
 * outside the training team gets `allowed: false` and a sentence, never an
 * error). Writes go through the board's one verb, `pb.training.act`.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const TILE_ORDER = ["expiring_30", "expiring_60", "expiring_90", "expired", "valid", "no_expiry"];
const MAX_BYTES = 10 * 1024 * 1024;

function blankForm() {
    return { name: "", kind: "CERT", source: "upload", issuer: "", reference: "",
             issue_date: "", expiry_date: "", hours: "", file_name: "", file_b64: "" };
}

export class PbCertificatesLens extends Component {
    static template = "pb_training.PbCertificatesLens";
    static props = {
        embedded: { type: Boolean, optional: true },
        startFilter: { type: String, optional: true },
        "*": true,
    };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.state = useState({
            loaded: false,
            failed: false,
            busy: false,
            data: { rows: [], tiles: [] },
            filter: this.props.startFilter || "",
            q: "",
            department_id: 0,
            job_id: 0,
            page: 1,
            drawer: false,
            form: blankForm(),
            person: null,
            peopleTerm: "",
            people: [],
            saving: false,
            acting: 0,
        });
        onWillStart(() => this.load());
    }

    ic(n, s = 16) { return ic(n, s); }

    // ------------------------------------------------------------- reading
    filters() {
        return {
            state: this.state.filter || "",
            q: this.state.q || "",
            department_id: Number(this.state.department_id) || 0,
            job_id: Number(this.state.job_id) || 0,
            page: this.state.page || 1,
        };
    }

    async load() {
        this.state.failed = false;
        this.state.busy = true;
        try {
            this.state.data = await this.orm.call("pb.training", "certificates_board", [this.filters()]);
        } catch (e) {
            console.warn("pb_training: the certificate register could not be read", e);
            this.state.failed = true;
        } finally {
            this.state.loaded = true;
            this.state.busy = false;
        }
    }

    async retry() {
        this.state.loaded = false;
        await this.load();
    }

    get data() { return this.state.data || {}; }
    get allowed() { return this.data.allowed !== false; }
    get rows() { return this.data.rows || []; }

    // ------------------------------------------------------------- tiles
    tileLabel(key) {
        return {
            expiring_30: _t("Expire within 30 days"),
            expiring_60: _t("Expire within 60 days"),
            expiring_90: _t("Expire within 90 days"),
            expired: _t("Expired"),
            valid: _t("In date"),
            no_expiry: _t("Never expire"),
        }[key] || key;
    }

    tileIcon(key) {
        return { expired: "triangleAlert", valid: "checkCircle", no_expiry: "circle" }[key] || "hourglass";
    }

    tileClass(tile) {
        const on = this.state.filter === tile.key;
        const n = tile.count || 0;
        return {
            "is-on": on,
            "is-zero": !n,
            "is-warn": !!n && tile.key.startsWith("expiring"),
            "is-bad": !!n && tile.key === "expired",
            "is-good": !!n && tile.key === "valid",
        };
    }

    get tiles() {
        const byKey = Object.fromEntries((this.data.tiles || []).map((t) => [t.key, t]));
        return TILE_ORDER.map((k) => byKey[k] || { key: k, count: 0 });
    }

    async setFilter(key) {
        this.state.filter = this.state.filter === key ? "" : key;
        this.state.page = 1;
        await this.load();
    }

    onSearch(ev) {
        this.state.q = ev.target.value;
        clearTimeout(this._searchTimer);
        this._searchTimer = setTimeout(() => { this.state.page = 1; this.load(); }, 250);
    }

    async onSelect(field, ev) {
        this.state[field] = Number(ev.target.value) || 0;
        this.state.page = 1;
        await this.load();
    }

    get anyFilter() {
        return !!(this.state.filter || this.state.q || this.state.department_id || this.state.job_id);
    }

    async clearFilters() {
        Object.assign(this.state, { filter: "", q: "", department_id: 0, job_id: 0, page: 1 });
        await this.load();
    }

    async goPage(delta) {
        const next = (this.state.page || 1) + delta;
        if (next < 1 || next > (this.data.pages || 1)) { return; }
        this.state.page = next;
        await this.load();
    }

    get pageWords() {
        return _t("Page %s of %s", this.data.page || 1, this.data.pages || 1);
    }

    get shownWords() {
        const n = this.data.total || 0;
        return n === 1 ? _t("1 certificate shown") : _t("%s certificates shown", n);
    }

    // ------------------------------------------------------------- rows
    stateClass(row) {
        return { expired: "is-bad", soon: "is-warn", valid: "is-ok", none: "", renewed: "is-old" }[row.state] || "";
    }

    canRefresh(row) {
        return this.data.can_write && row.channel_id && row.state !== "renewed"
            && !(row.renewal && row.renewal.open);
    }

    async act(verb, payload, row) {
        this.state.acting = row ? row.id : -1;
        try {
            const res = await this.orm.call("pb.training", "act", [verb, payload]);
            if (res && res.message) { this.notif.add(res.message, { type: "success" }); }
            await this.load();
            return res;
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not work."), { type: "danger" });
            return null;
        } finally {
            this.state.acting = 0;
        }
    }

    refresher(row) { return this.act("assign_refresher", { document_id: row.id }, row); }
    verify(row) { return this.act("verify_certificate", { document_id: row.id }, row); }
    download(row) { if (row.download_url) { window.open(row.download_url, "_blank", "noopener"); } }
    goMine() { window.location.assign("/my/training/certificates"); }
    record(row) { window.open(`/my/training/record.pdf?employee_id=${row.employee_id}`, "_blank", "noopener"); }

    // ------------------------------------------------------------- drawer
    async openDrawer() {
        Object.assign(this.state, { drawer: true, form: blankForm(), person: null, peopleTerm: "", people: [] });
        await this.searchPeople();
    }

    closeDrawer() { this.state.drawer = false; }

    async searchPeople() {
        try {
            this.state.people = await this.orm.call("pb.training", "certificate_people", [this.state.peopleTerm]);
        } catch (e) {
            console.warn("pb_training: the people search failed", e);
            this.state.people = [];
        }
    }

    onPeopleTerm(ev) {
        this.state.peopleTerm = ev.target.value;
        clearTimeout(this._peopleTimer);
        this._peopleTimer = setTimeout(() => this.searchPeople(), 220);
    }

    pickPerson(emp) { this.state.person = emp; }
    clearPerson() { this.state.person = null; }

    setField(field, ev) { this.state.form[field] = ev.target.value; }

    onFile(ev) {
        const file = ev.target.files && ev.target.files[0];
        const form = this.state.form;
        form.file_name = "";
        form.file_b64 = "";
        if (!file) { return; }
        if (file.size > MAX_BYTES) {
            this.notif.add(_t("The file is bigger than 10 MB."), { type: "danger" });
            ev.target.value = "";
            return;
        }
        const reader = new FileReader();
        reader.onload = () => {
            const res = String(reader.result || "");
            form.file_name = file.name;
            form.file_b64 = res.includes(",") ? res.split(",")[1] : res;
        };
        reader.readAsDataURL(file);
    }

    get canSave() {
        const f = this.state.form;
        return !!(this.state.person && f.name.trim() && f.file_b64 && !this.state.saving
                  && (f.kind !== "LIC" || f.expiry_date));
    }

    async save() {
        if (!this.canSave) { return; }
        this.state.saving = true;
        try {
            const res = await this.orm.call("pb.training", "act", ["add_certificate",
                { ...this.state.form, employee_id: this.state.person.id }]);
            this.notif.add((res && res.message) || _t("Added."), { type: "success" });
            this.state.drawer = false;
            await this.load();
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not work."), { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }
}
