/** @odoo-module **/

import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

import {
    amount, bandRange, bandRows, effectiveRate, group, percentFromRate,
    rateFromPercent, showValue, taxFor, validateBands,
} from "./tax_math";

/**
 * Tax and the protections that come with pay.
 *
 * One page that answers, in order: where do these numbers come from, what are
 * the bands, what relief and what ceilings, and — the part that makes it real —
 * what does changing any of them do to somebody's take-home pay, which the
 * panel on the right answers within a second of every save.
 *
 * Nothing here decides anything. Whether a schedule is coherent, whether this
 * configuration may still be edited, whether a value is a percentage: the
 * server answers all of those, and this only shows the answer early so a person
 * is not told "no" after pressing Save.
 */
export class TaxTab extends Component {
    static template = "pb_blueprint.TaxTab";
    static props = {
        configId: { type: Number },
        revision: { type: Number, optional: true },
        currency: { type: String, optional: true },
        reloadKey: { type: Number, optional: true },
        onChanged: { type: Function },
        onRevision: { type: Function },
        onGrid: { type: Function },
        onComponents: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");

        this.state = useState({
            loading: true,
            error: "",
            data: null,
            tableId: null,
            bands: [],          // the working copy: [{lower, rate}]
            bandsDirty: false,
            bandError: "",
            tryIncome: 40000000,
            values: {},         // {CODE: "typed text"} — only what was touched
            prefs: { basis: "actual", rounding: "0" },
            busy: false,
            syncOpen: false,
            sourceOpen: false,
            routesOpen: false,
        });

        onWillStart(async () => {
            await this.load();
            this.state.loading = false;
        });

        onWillUpdateProps(async (next) => {
            if (next.reloadKey !== this.props.reloadKey) {
                await this.load();
            }
        });
    }

    ic(name, size = 16) { return ic(name, size); }

    async rpc(method, args) {
        try {
            return await this.orm.call("pb.blueprint.studio", method, args || []);
        } catch (e) {
            const reason = (e && e.data && e.data.message) || (e && e.message) || "";
            this.notif.add(reason || _t("The server could not be reached."),
                           { type: "danger" });
            return { ok: false, reason };
        }
    }

    async load() {
        const res = await this.rpc("bp_tax_data", [this.props.configId]);
        if (!res || !res.ok) {
            this.state.error = (res && res.reason)
                || _t("The tax settings could not be loaded.");
            return;
        }
        this.state.error = "";
        this.state.data = res;
        this.state.prefs = { ...res.prefs };
        this.state.values = {};
        const table = this.pickTable(res.tables);
        this.state.tableId = table ? table.id : null;
        // BP3 — the bands are rebuilt on every save, so the ids the server just
        // handed back are already stale. Only the numbers are kept.
        this.state.bands = table
            ? table.brackets.map((b) => ({ lower: b.lower, rate: b.rate }))
            : [];
        this.state.bandsDirty = false;
        this.state.bandError = "";
        if (res.revision !== undefined) this.props.onRevision(res.revision);
    }

    /** The table the income tax actually uses, when there is more than one. */
    pickTable(tables) {
        const list = tables || [];
        if (!list.length) return null;
        if (this.state.tableId) {
            const kept = list.find((t) => t.id === this.state.tableId);
            if (kept) return kept;
        }
        return list.find((t) => (t.used_by || []).includes("PIT")) || list[0];
    }

    /** Switch to another band table, dropping any unsaved edits to this one. */
    setTable(id) {
        const table = (this.tables || []).find((t) => t.id === id);
        if (!table) return;
        this.state.tableId = id;
        this.state.bands = table.brackets.map((b) => ({ lower: b.lower, rate: b.rate }));
        this.state.bandsDirty = false;
        this.state.bandError = "";
    }

    // ==================================================================
    // Reading
    // ==================================================================
    get data() { return this.state.data || {}; }
    get editable() { return !!this.data.editable; }
    get pack() { return this.data.pack || null; }
    get tables() { return this.data.tables || []; }
    get table() { return this.pickTable(this.tables); }
    get rows() { return bandRows(this.state.bands); }
    get drift() { return this.data.drift || []; }
    get unmatched() { return this.data.unmatched || []; }
    get relief() { return (this.data.values || {}).relief || []; }
    get insurance() { return (this.data.values || {}).insurance || []; }
    get routes() { return (this.data.values || {}).routes || []; }
    get currency() { return this.props.currency || this.data.currency || ""; }

    get packStatusLabel() {
        const n = this.drift.length;
        if (this.data.status === "na") return _t("No rule pack for this country");
        if (this.data.status === "aligned") return _t("Aligned with the pack");
        return n === 1
            ? _t("1 value differs from the pack")
            : _t("%s values differ from the pack", n);
    }

    get packStatusClass() {
        return { aligned: "ok", drift: "warn", na: "muted" }[this.data.status] || "muted";
    }

    get packLine() {
        const p = this.pack;
        if (!p) return "";
        const bits = [p.name];
        if (p.version) bits.push(_t("version %s", p.version));
        if (p.effective_date) {
            bits.push(_t("in force from %s", this.longDate(p.effective_date)));
        }
        return bits.join(" · ");
    }

    longDate(iso) {
        const parts = String(iso || "").split("-");
        if (parts.length !== 3) return iso || "";
        const months = [_t("January"), _t("February"), _t("March"), _t("April"),
                        _t("May"), _t("June"), _t("July"), _t("August"),
                        _t("September"), _t("October"), _t("November"),
                        _t("December")];
        return `${Number(parts[2])} ${months[Number(parts[1]) - 1]} ${parts[0]}`;
    }

    group(value) { return group(value); }
    showValue(value, format) { return showValue(value, format); }
    bandRange(row) { return bandRange(row, (n) => group(n)); }
    percent(rate) { return percentFromRate(rate); }

    // ==================================================================
    // The bands
    // ==================================================================
    get bandsValid() { return !validateBands(this.state.bands); }

    get canSaveBands() {
        return this.editable && this.state.bandsDirty && this.bandsValid
            && !this.state.busy;
    }

    onBandLower(index, ev) {
        const value = amount(ev.target.value);
        if (value === null) {
            this.state.bandError = _t("A band starts at an amount.");
            return;
        }
        this.state.bands[index].lower = value;
        this.markBands();
    }

    onBandRate(index, ev) {
        const rate = rateFromPercent(ev.target.value);
        if (rate === null) {
            this.state.bandError = _t("A rate is a percentage between 0 and 100.");
            return;
        }
        this.state.bands[index].rate = rate;
        this.markBands();
    }

    /** Rows settle into order when the caret leaves, never while typing. */
    onBandBlur() {
        if (!this.state.bandsDirty) return;
        this.state.bands = [...this.state.bands].sort(
            (a, b) => Number(a.lower) - Number(b.lower));
    }

    markBands() {
        this.state.bandsDirty = true;
        this.state.bandError = validateBands(this.state.bands);
    }

    addBand() {
        const rows = this.rows;
        const last = rows[rows.length - 1];
        const start = last ? Number(last.lower) + 5000000 : 0;
        this.state.bands = [...this.state.bands,
                            { lower: start, rate: last ? last.rate : 0.05 }];
        this.markBands();
    }

    removeBand(index) {
        this.state.bands = this.state.bands.filter((_b, i) => i !== index);
        this.markBands();
    }

    async saveBands() {
        if (!this.canSaveBands) return;
        this.state.busy = true;
        const res = await this.rpc("bp_tax_save_bands", [
            this.props.configId, this.state.tableId,
            this.state.bands.map((b) => ({ lower: Number(b.lower), rate: Number(b.rate) })),
            this.props.revision]);
        this.state.busy = false;
        if (!res || !res.ok) {
            this.state.bandError = (res && res.reason)
                || _t("The bands could not be saved.");
            if (res && res.conflict) this.props.onChanged({ conflict: true });
            return;
        }
        if (res.revision !== undefined) this.props.onRevision(res.revision);
        await this.load();
        this.props.onChanged(res);
        this.notif.add(_t("The bands are saved. The pay panel has been brought up to date."),
                       { type: "success" });
    }

    // ==================================================================
    // Try an income
    // ==================================================================
    get tryTax() { return taxFor(this.state.bands, this.state.tryIncome); }

    get tryRate() {
        return Math.round(effectiveRate(this.state.bands, this.state.tryIncome) * 1000) / 10;
    }

    onTry(ev) {
        const value = amount(ev.target.value);
        if (value !== null) this.state.tryIncome = Math.max(0, value);
    }

    /** Which band the tried income lands in, so the table can highlight it. */
    isTryBand(row) {
        const value = Number(this.state.tryIncome) || 0;
        if (value <= 0) return false;
        return value > row.lower && (row.upper === null || value <= row.upper);
    }

    // ==================================================================
    // The values
    // ==================================================================
    typed(row) {
        if (this.state.values[row.code] !== undefined) {
            return this.state.values[row.code];
        }
        return row.number_format === "percentage"
            ? String(percentFromRate(row.value))
            : String(row.value);
    }

    onValue(row, ev) {
        this.state.values[row.code] = ev.target.value;
    }

    valueError(row) {
        const raw = this.state.values[row.code];
        if (raw === undefined) return "";
        const n = row.number_format === "percentage"
            ? rateFromPercent(raw) : amount(raw);
        if (n === null) return _t("That is not a number.");
        if (n < 0) return _t("This cannot be negative.");
        if (row.number_format === "percentage" && n > 1) {
            return _t("A rate is a percentage between 0 and 100.");
        }
        return "";
    }

    get valuesDirty() {
        return Object.keys(this.state.values).length > 0;
    }

    get valuesValid() {
        for (const row of [...this.relief, ...this.insurance, ...this.routes]) {
            if (this.valueError(row)) return false;
        }
        return true;
    }

    get canSaveValues() {
        return this.editable && !this.state.busy
            && (this.valuesDirty || this.prefsDirty) && this.valuesValid;
    }

    get prefsDirty() {
        const saved = (this.data.prefs || {});
        return this.state.prefs.basis !== saved.basis
            || this.state.prefs.rounding !== saved.rounding;
    }

    /** The pack's own figure, when this value has drifted from it. */
    packHint(row) {
        if (!row.differs || row.pack === null || row.pack === undefined) return "";
        return _t("pack: %s", showValue(row.pack, row.number_format));
    }

    restorePack(row) {
        if (row.pack === null || row.pack === undefined) return;
        this.state.values[row.code] = row.number_format === "percentage"
            ? String(percentFromRate(row.pack)) : String(row.pack);
    }

    setPref(key, value) {
        this.state.prefs[key] = value;
    }

    async saveValues() {
        if (!this.canSaveValues) return;
        const values = {};
        for (const row of [...this.relief, ...this.insurance, ...this.routes]) {
            const raw = this.state.values[row.code];
            if (raw === undefined) continue;
            values[row.code] = row.number_format === "percentage"
                ? rateFromPercent(raw) : amount(raw);
        }
        this.state.busy = true;
        const res = await this.rpc("bp_tax_save_values", [
            this.props.configId, values, { ...this.state.prefs },
            this.props.revision]);
        this.state.busy = false;
        if (!res || !res.ok) {
            this.notif.add((res && res.reason) || _t("Those values could not be saved."),
                           { type: "danger", sticky: true });
            if (res && res.conflict) this.props.onChanged({ conflict: true });
            return;
        }
        if (res.revision !== undefined) this.props.onRevision(res.revision);
        await this.load();
        this.props.onChanged(res);
        this.notif.add(_t("Saved. The pay panel has been brought up to date."),
                       { type: "success" });
    }

    // ==================================================================
    // Taking the pack's values
    // ==================================================================
    openSync() { this.state.syncOpen = true; }
    closeSync() { this.state.syncOpen = false; }

    async doSync() {
        this.state.syncOpen = false;
        this.state.busy = true;
        const res = await this.rpc("bp_tax_sync_pack",
                                   [this.props.configId, this.props.revision]);
        this.state.busy = false;
        if (!res || !res.ok) {
            this.notif.add((res && res.reason) || _t("The pack's values could not be taken."),
                           { type: "warning", sticky: true });
            return;
        }
        if (res.revision !== undefined) this.props.onRevision(res.revision);
        await this.load();
        this.props.onChanged(res);
        this.notif.add(res.applied.length === 1
            ? _t("1 value now matches the pack.")
            : _t("%s values now match the pack.", res.applied.length),
            { type: "success" });
    }

    toggleSource() { this.state.sourceOpen = !this.state.sourceOpen; }
    toggleRoutes() { this.state.routesOpen = !this.state.routesOpen; }

    onKeydown(ev) {
        // The journey shell treats Enter as "continue to the next step". A
        // number field where Enter walks off the page is a field nobody can
        // correct a typo in (BP20).
        if (ev.key === "Enter") ev.stopPropagation();
    }
}
