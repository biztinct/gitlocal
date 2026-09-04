/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * NETROLE P2 — the category review.
 *
 * An Excel scheme arrives with every component on the same shelf. The formulas
 * in it already say what each one DOES to net pay — what net adds, what it
 * subtracts, what never reaches it at all — and the engine reads exactly that
 * (`suggest_categories`, which writes nothing). This screen is where that
 * reading becomes a decision instead of a guess.
 *
 * Three rules the surface exists to keep:
 *
 * 1. Nothing is written until somebody presses Apply, and then only the ticked
 *    rows. Skip is a first-class answer and leaves the scheme untouched.
 * 2. Two opinions are shown at once. Ours comes from the arithmetic; theirs is
 *    the coloured band they typed above the column in their own workbook. Where
 *    those disagree the row arrives UNTICKED with the disagreement spelled out.
 * 3. Whatever was going to happen after the import still happens: `next_action`
 *    is carried through and dispatched when this screen closes, either way.
 */
export class PbCategoryReview extends Component {
    static template = "pb_formula_studio.PbCategoryReview";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            busy: false,
            failed: false,
            data: null,
            netPick: null,
        });
        onWillStart(() => this.load());
    }

    // ---- params -----------------------------------------------------------
    get params() {
        const a = this.props.action || {};
        return a.params || (a.context && a.context.params) || {};
    }
    get configId() {
        const p = this.params;
        const ctx = (this.props.action && this.props.action.context) || {};
        return parseInt(p.config_id || ctx.config_id || 0, 10);
    }
    get nextAction() {
        return this.params.next_action || null;
    }

    async load() {
        this.state.loading = true;
        this.state.failed = false;
        try {
            this.state.data = await this.orm.call(
                "pb.formula.studio", "category_review_data", [this.configId]);
            const cands = (this.state.data && this.state.data.net_candidates) || [];
            this.state.netPick = cands.length ? cands[0].id : null;
        } catch (e) {
            this.state.failed = true;
        } finally {
            this.state.loading = false;
        }
    }

    // ---- derived ----------------------------------------------------------
    get data() { return this.state.data || {}; }
    get groups() { return this.data.groups || []; }
    get rows() {
        const out = [];
        for (const g of this.groups) { for (const r of g.rows) out.push(r); }
        return out;
    }
    get acceptedIds() { return this.rows.filter(r => r.accept).map(r => r.id); }
    get acceptedCount() { return this.acceptedIds.length; }
    get hasRows() { return this.rows.length > 0; }
    get canEdit() { return !!this.data.can_edit; }
    get netless() { return !!this.data.error; }
    get netCandidates() { return this.data.net_candidates || []; }

    // A subtitle that names the component the reading is anchored on, because
    // "we read your formula" is only reassuring when it says WHICH one.
    get anchorSentence() {
        const code = this.data.net_code;
        if (!code) {
            return _t("Here is what each component does to net pay.");
        }
        return _t(
            "We read %(net)s. Here is what each component does to net pay.",
            { net: this.data.net_name ? `${this.data.net_name} (${code})` : code });
    }

    // ---- ticking ----------------------------------------------------------
    toggleRow(row) { row.accept = !row.accept; }
    setAll(accept) { for (const r of this.rows) r.accept = accept; }
    acceptAll() { this.setAll(true); }
    clearAll() { this.setAll(false); }
    setGroup(group, accept) { for (const r of group.rows) r.accept = accept; }
    acceptGroup(group) { this.setGroup(group, true); }
    clearGroup(group) { this.setGroup(group, false); }
    groupAcceptedCount(group) { return group.rows.filter(r => r.accept).length; }

    confidenceLabel(row) {
        if (row.confidence === "certain") return _t("Certain");
        if (row.confidence === "likely") return _t("Likely");
        return _t("Needs review");
    }

    // ---- leaving ----------------------------------------------------------
    /**
     * Whatever the import was going to do next still happens. With no chained
     * action (the studio command, the structure's own Actions menu) this lands
     * back in the Formula Studio on the same scheme — a door that returns you
     * somewhere else is a door people stop walking through.
     */
    _leave() {
        const next = this.nextAction;
        if (next) { return this.action.doAction(next); }
        return this.action.doAction({
            type: "ir.actions.client",
            tag: "pb_formula_studio",
            params: { config_id: this.configId },
            context: { config_id: this.configId },
        });
    }
    skip() { return this._leave(); }

    async apply() {
        const ids = this.acceptedIds;
        if (!ids.length) { return this._leave(); }
        this.state.busy = true;
        try {
            const r = await this.orm.call(
                "pb.formula.studio", "category_review_apply", [this.configId, ids]);
            const n = (r && r.applied) || 0;
            this.notif.add(
                n ? _t("%s component(s) refiled", n)
                  : _t("Everything was already filed that way."),
                { type: "success" });
            await this._leave();
        } catch (e) {
            this.notif.add(_t("Those categories could not be saved."), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // ---- the netless path -------------------------------------------------
    onNetPick(ev) { this.state.netPick = parseInt(ev.target.value, 10) || null; }
    async confirmNet() {
        if (!this.state.netPick) { return; }
        this.state.busy = true;
        try {
            this.state.data = await this.orm.call(
                "pb.formula.studio", "category_review_set_net",
                [this.configId, this.state.netPick]);
        } catch (e) {
            this.notif.add(_t("That component could not be set as net pay."),
                { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
}

registry.category("actions").add("pb_category_review", PbCategoryReview);
