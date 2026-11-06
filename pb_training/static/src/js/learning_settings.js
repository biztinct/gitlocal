/** @odoo-module **/
/**
 * Settings › HR › LEARNING (LEARNING L6) — every Learning switch that had no
 * screen, on five tabs: Report pack · Reminders · Feedback · Country packs ·
 * Day one. Each Settings card opens this screen on its own tab
 * (`pb_settings_tab` in the action's context).
 *
 * HERO MOMENT: every switch says, right under it, what it will do — with its
 * own numbers ("Reminders go to the person 3, 1 and 0 days before the date,
 * then every 3 days; the manager after 2 days late; the HR lead after 5.").
 * The sentence is worked out on the server, so the screen and the morning job
 * read the same values.
 *
 * Reads `pb.training.settings_get()`; writes `settings_set(values)` (head of
 * training only — a training manager sees the screen read-only). The pack tab
 * previews the email and sends a test copy to the person pressing it, nobody
 * else (`pb.training.pack.preview()` / `send_test()`). Country packs is the
 * L2 screen, embedded without its own switches.
 */
import { Component, markup, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { PbRequiredSettings } from "@pb_training/js/required_settings";

export const SETTINGS_TAB_KEY = "pb_settings_tab";

const TABS = [
    { key: "report_pack", icon: "mail", label: _t("Report pack") },
    { key: "reminders", icon: "bell", label: _t("Reminders") },
    { key: "feedback", icon: "messageSquare", label: _t("Feedback") },
    { key: "country_packs", icon: "globe", label: _t("Country packs") },
    { key: "day_one", icon: "sunrise", label: _t("Day one") },
];

export class PbLearningSettings extends Component {
    static template = "pb_training.PbLearningSettings";
    static components = { PbRequiredSettings };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.tabs = TABS;
        const ctx = (this.props.action && this.props.action.context) || {};
        const asked = ctx[SETTINGS_TAB_KEY];
        this.state = useState({
            loaded: false, failed: false, d: {}, form: {}, tab: TABS.some((t) => t.key === asked) ? asked : "report_pack",
            saving: false, testing: false, preview: null, previewing: false, emailError: "",
        });
        onWillStart(() => this.load());
    }

    ic(n, s = 16) { return ic(n, s); }

    async load() {
        this.state.failed = false;
        try {
            const d = await this.orm.call("pb.training", "settings_get", []);
            this.state.d = d || {};
            this.state.form = Object.assign({}, (d && d.values) || {});
        } catch (e) {
            console.warn("pb_training: the Learning settings could not be read", e);
            this.state.failed = true;
        } finally {
            this.state.loaded = true;
        }
    }

    async retry() {
        this.state.loaded = false;
        await this.load();
    }

    get d() { return this.state.d || {}; }
    get allowed() { return this.d.allowed !== false; }
    get canWrite() { return !!this.d.can_write; }
    get words() { return this.d.words || {}; }
    get pack() { return this.d.pack || {}; }

    pickTab(key) { this.state.tab = key; }

    /** A switch: flips the value on the form (saved with Save). */
    flip(key) {
        if (!this.canWrite) { return; }
        this.state.form[key] = !this.state.form[key];
    }

    setNum(key, ev) { this.state.form[key] = Number(ev.target.value) || 0; }
    setText(key, ev) { this.state.form[key] = ev.target.value; }

    /** Addresses checked as they are typed: the Save is refused otherwise. */
    get emailList() {
        return String(this.state.form.report_pack_email || "").split(/[,;\s]+/).map((x) => x.trim()).filter(Boolean);
    }

    get emailProblem() {
        const bad = this.emailList.find((x) => !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(x));
        if (bad) { return _t("%s is not an email address.", bad); }
        const cap = this.d.mail_cap || 20;
        if (this.emailList.length > cap) { return _t("The pack goes to at most %s addresses.", cap); }
        return "";
    }

    get dirty() {
        const v = this.d.values || {};
        return Object.keys(this.state.form).some((k) => String(this.state.form[k]) !== String(v[k]));
    }

    async save() {
        if (this.emailProblem) { return; }
        this.state.saving = true;
        try {
            const res = await this.orm.call("pb.training", "settings_set", [this.state.form]);
            this.state.d = res || {};
            this.state.form = Object.assign({}, (res && res.values) || {});
            this.notif.add((res && res.message) || _t("Saved."), { type: "success" });
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not work."), { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    undo() { this.state.form = Object.assign({}, this.d.values || {}); }

    async sendTest() {
        this.state.testing = true;
        try {
            const res = await this.orm.call("pb.training.pack", "send_test", []);
            this.notif.add((res && res.message) || _t("Sent."), { type: "success" });
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not work."), { type: "danger" });
        } finally {
            this.state.testing = false;
        }
    }

    async openPreview() {
        this.state.previewing = true;
        try {
            const res = await this.orm.call("pb.training.pack", "preview", []);
            // R51: server-built HTML from our own template, wrapped once.
            this.state.preview = Object.assign({}, res, { body: markup(res.html || "") });
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("The preview could not be built."), { type: "danger" });
        } finally {
            this.state.previewing = false;
        }
    }

    closePreview() { this.state.preview = null; }

    get heroWords() { return _t("How Learning behaves for %s", this.d.company || ""); }

    get capWords() { return _t("Email addresses, separated by commas. At most %s.", this.d.mail_cap || 20); }

    get previewToWords() {
        const to = (this.state.preview && this.state.preview.to) || [];
        return to.length ? _t("To: %s", to.join(", ")) : _t("Nobody is set to receive it yet.");
    }

    get testWords() {
        const me = this.d.my_email;
        return me ? _t("A copy goes to %s only.", me) : _t("Add an email address to your profile to get a test copy.");
    }

    get packStatusWords() {
        const p = this.pack;
        if (!p.next_label) { return ""; }
        return p.sent_already ? _t("The %s pack has already gone out.", p.next_label) : _t("Next pack: %s.", p.next_label);
    }
}

registry.category("actions").add("pb_training_settings", PbLearningSettings);
