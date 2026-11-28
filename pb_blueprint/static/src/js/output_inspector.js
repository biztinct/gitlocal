/** @odoo-module **/

import { Component, useState, useRef, onWillStart, onWillUpdateProps,
         useEffect } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

import { fmtValue, groupLabel, badgeLabel, chainMore } from "./outputs_text";
import { SentenceEditor } from "./sentence_editor";

/**
 * One component, opened: where its number comes from and where it goes.
 *
 * A side sheet rather than a dialog, because the table stays visible behind it
 * and a chip in here jumps to a row out there. Four questions, in the order
 * somebody asks them:
 *
 *   1. what is this, and what did it pay the sample employee;
 *   2. how was it worked out — the calculation in codes, each one a chip you
 *      can follow;
 *   3. what feeds it and what it feeds, one step away and then the whole chain;
 *   4. what the engine actually did, read by read, for this sample.
 *
 * For a component somebody wrote as Excel it also shows the guided version
 * beside theirs, and offers to go back to it — that is the one irreversible
 * looking thing on the step, so it says exactly what will change first.
 */
export class OutputInspector extends Component {
    static template = "pb_blueprint.OutputInspector";
    static components = { SentenceEditor };
    static props = {
        configId: { type: Number },
        ruleId: { type: Number },
        revision: { type: Number, optional: true },
        sampleId: { type: [Number, Boolean], optional: true },
        sampleName: { type: String, optional: true },
        currency: { type: String, optional: true },
        onClose: { type: Function },
        onJump: { type: Function },
        onChanged: { type: Function },
        onGrid: { type: Function },
    };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.sheetRef = useRef("sheet");

        this.state = useState({
            loading: true,
            error: "",
            data: null,
            chain: "",            // "" | "from" | "into"
            busy: false,
            editing: false,
            confirmRestore: false,
        });

        onWillStart(() => this.load());
        onWillUpdateProps(async (next) => {
            if (next.ruleId !== this.props.ruleId) {
                this.state.chain = "";
                this.state.editing = false;
                await this.load(next.ruleId);
            }
        });

        // A hand-built sheet is not a framework Dialog: nothing claims focus,
        // so Escape reaches nothing (BP20). It takes focus on mount.
        useEffect((el) => { if (el) { el.focus(); } }, () => [this.sheetRef.el]);
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

    async load(ruleId) {
        this.state.loading = true;
        const res = await this.rpc("bp_output_detail", [
            this.props.configId, ruleId || this.props.ruleId,
            this.props.sampleId || false]);
        this.state.loading = false;
        if (!res || !res.ok) {
            this.state.error = (res && res.reason)
                || _t("This component could not be opened.");
            this.state.data = null;
            return;
        }
        this.state.error = "";
        this.state.data = res;
    }

    // ==================================================================
    // Reading
    // ==================================================================
    get data() { return this.state.data || {}; }
    get rule() { return this.data.rule || {}; }

    get groupWord() { return groupLabel(this.rule.group); }

    get sourceWord() {
        if (this.rule.column_type === "input") { return badgeLabel("input"); }
        if (this.rule.column_type === "constant") { return badgeLabel("constant"); }
        return badgeLabel(this.rule.source === "generated" ? "generated" : "manual");
    }

    value(v) { return fmtValue(v); }

    get headlineValue() {
        if (this.rule.column_type === "constant") {
            return fmtValue(this.rule.constant_value);
        }
        return fmtValue(this.rule.value);
    }

    get formula() {
        if (this.rule.column_type === "input") {
            return _t("This is a number the payroll is given. Nothing works it out.");
        }
        if (this.rule.column_type === "constant") {
            return _t("A fixed value: %s", fmtValue(this.rule.constant_value));
        }
        return this.data.formula_codes || _t("Nothing is worked out yet.");
    }

    get isFormula() { return this.rule.column_type === "formula"; }

    get chips() { return this.data.chips || []; }

    get feedsFrom() { return this.data.feeds_from || []; }
    get feedsInto() { return this.data.feeds_into || []; }

    get chainNodes() {
        const chain = this.data.chain || {};
        const side = this.state.chain === "into" ? chain.into : chain.from;
        return (side || {}).nodes || [];
    }

    get chainMoreLine() {
        const chain = this.data.chain || {};
        const side = this.state.chain === "into" ? chain.into : chain.from;
        return chainMore((side || {}).more);
    }

    toggleChain(which) {
        this.state.chain = this.state.chain === which ? "" : which;
    }

    get feedsFromLine() {
        const n = this.feedsFrom.length;
        if (!n) {
            return this.isFormula
                ? _t("This calculation reads nothing from other components.")
                : _t("Nothing feeds this — the payroll is given it.");
        }
        return n === 1 ? _t("1 component feeds this")
                       : _t("%s components feed this", n);
    }

    get feedsIntoLine() {
        const n = this.feedsInto.length;
        if (!n) {
            return _t("Nothing else uses this value yet.");
        }
        return n === 1 ? _t("1 component uses this")
                       : _t("%s components use this", n);
    }

    get trace() { return this.data.trace || { available: false, reads: [] }; }

    get traceLine() {
        const t = this.trace;
        if (!t.available) { return ""; }
        const reads = (t.reads || []).map(
            (r) => `${r.name || r.code} ${fmtValue(r.value)}`);
        const left = reads.join(" · ");
        return left
            ? `${left} → ${fmtValue(t.value)}`
            : String(_t("Worked out to %s", fmtValue(t.value)));
    }

    get differs() { return !!this.data.differs; }

    get review() { return this.data.review || []; }

    // ==================================================================
    // Doing something about it
    // ==================================================================
    onJump(chip) { this.props.onJump(chip.id); }

    openEditor() { this.state.editing = true; }

    closeEditor() { this.state.editing = false; }

    async onEditorSaved(res) {
        this.state.editing = false;
        await this.load();
        this.props.onChanged(res);
        this.notif.add(_t("Saved. The numbers have been worked out again."),
                       { type: "success" });
    }

    async onEditorRemoved() {
        // Removing belongs to the Pay rules step, where the tray that puts it
        // back is. Saying so is better than a second, quieter way to do it.
        this.state.editing = false;
        this.notif.add(
            _t("Components are removed on the Pay rules step, where the list of removed ones lives."),
            { type: "info" });
    }

    askRestore() { this.state.confirmRestore = true; }

    async doRestore() {
        this.state.confirmRestore = false;
        this.state.busy = true;
        const res = await this.rpc("bp_component_restore_guided",
                                   [this.props.ruleId, this.props.revision || 0]);
        this.state.busy = false;
        if (!res || !res.ok) {
            this.notif.add((res && res.reason)
                || _t("The guided version could not be brought back."),
                { type: "warning", sticky: true });
            return;
        }
        await this.load();
        this.props.onChanged(res);
        this.notif.add(_t("Back to the guided version."), { type: "success" });
    }

    onKeydown(ev) {
        // The sheet's keys stop here: the journey shell treats Enter as
        // "continue to the next step" and Escape has to close this, not
        // something behind it (BP20).
        if (ev.key === "Escape") {
            ev.stopPropagation();
            if (this.state.confirmRestore) { this.state.confirmRestore = false; return; }
            if (this.state.editing) { this.state.editing = false; return; }
            this.props.onClose();
            return;
        }
        if (ev.key === "Enter") { ev.stopPropagation(); }
    }
}
