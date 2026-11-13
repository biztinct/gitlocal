/** @odoo-module **/
/**
 * Settings › HR › REQUIRED TRAINING (LEARNING L2).
 *
 * HERO MOMENT: the four country packs as switches, each with one line saying
 * what it brings and a "Review the rules" door into Learning › Required ›
 * Rules filtered on that pack. Switching a pack on copies its rules into this
 * company with "assign it by itself" off — nothing reaches anybody until HR
 * turns a rule on (safety rail 4).
 *
 * Under it, the three switches that used to have no screen: the renewal
 * window (days), the morning job's cap on required courses, and the day-one
 * courses switch (moved here from nowhere — it was a system parameter).
 *
 * Reads `pb.training.required_settings`; writes through `pb.training.act`
 * (`switch_pack`, `save_required_settings`), training managers only. A
 * trainer sees the screen read-only.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { openHub } from "@pb_hub/js/hub_nav";
import { LEARNING_HUB_XMLID } from "@pb_learning_hub/js/learning_hub";

/** The context keys the Required lens reads its arrival from. */
export const REQ_TAB_KEY = "pb_training_req_tab";
export const REQ_STATE_KEY = "pb_training_req_state";
export const REQ_PACK_KEY = "pb_training_req_pack";

export class PbRequiredSettings extends Component {
    static template = "pb_training.PbRequiredSettings";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.state = useState({ loaded: false, failed: false, d: {}, form: {}, saving: false, switching: "" });
        onWillStart(() => this.load());
    }

    ic(n, s = 16) { return ic(n, s); }

    async load() {
        this.state.failed = false;
        try {
            const d = await this.orm.call("pb.training", "required_settings", []);
            this.state.d = d || {};
            this.state.form = { renew_before: d.renew_before, enforce_cap: d.enforce_cap, day1: !!d.day1 };
        } catch (e) {
            console.warn("pb_training: the required-training settings could not be read", e);
            this.state.failed = true;
        } finally {
            this.state.loaded = true;
        }
    }

    get d() { return this.state.d || {}; }
    get allowed() { return this.d.allowed !== false; }
    get canManage() { return !!this.d.can_manage; }

    packWords(pk) {
        const bits = [pk.rules === 1 ? _t("1 rule") : _t("%s rules", pk.rules)];
        if (pk.unverified) {
            bits.push(pk.unverified === 1 ? _t("1 to confirm before use") : _t("%s to confirm before use", pk.unverified));
        }
        if (pk.on) {
            bits.push(pk.active === 1 ? _t("1 switched on") : _t("%s switched on", pk.active));
        }
        return bits.join(" · ");
    }

    async toggle(pk) {
        if (!this.canManage) { return; }
        this.state.switching = pk.cc;
        try {
            const res = await this.orm.call("pb.training", "act", ["switch_pack", { cc: pk.cc, on: !pk.on }]);
            if (res && res.message) { this.notif.add(res.message, { type: "success" }); }
            await this.load();
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not work."), { type: "danger" });
        } finally {
            this.state.switching = "";
        }
    }

    review(pk) {
        openHub(this.action, {
            xmlid: LEARNING_HUB_XMLID,
            lens: "required",
            context: { [REQ_TAB_KEY]: "rules", [REQ_PACK_KEY]: pk.key },
        });
    }

    openMatrix() {
        openHub(this.action, { xmlid: LEARNING_HUB_XMLID, lens: "required", context: { [REQ_TAB_KEY]: "matrix" } });
    }

    setField(field, ev, kind = "int") {
        this.state.form[field] = kind === "bool" ? !!ev.target.checked : (Number(ev.target.value) || 0);
    }

    async save() {
        this.state.saving = true;
        try {
            const res = await this.orm.call("pb.training", "act", ["save_required_settings", this.state.form]);
            this.notif.add((res && res.message) || _t("Saved."), { type: "success" });
            await this.load();
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not work."), { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }
}

registry.category("actions").add("pb_training_required_settings", PbRequiredSettings);
