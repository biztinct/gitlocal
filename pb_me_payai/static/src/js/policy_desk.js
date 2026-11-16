/** @odoo-module **/
/**
 * Home › Policies (WDGAP S6-B, E5) — where HR uploads the company's policy
 * files and switches PayAI on for employees.
 *
 * One read (`pb.policy.desk.get_desk`), one write per press. The server
 * gates every call: the HR team manages files; switching on and the daily
 * limits are an HR manager's. Quiet board: grey at zero; colour only for the
 * one thing that would make it work (switch on, publish a file).
 */
import { Component, onWillStart, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { HOME_LENSES } from "@pb_home_hub/js/home_hub";

const MODEL = "pb.policy.desk";
const MAX_BYTES = 10 * 1024 * 1024;

export class PbPolicyDesk extends Component {
    static template = "pb_me_payai.PbPolicyDesk";
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.dialog = useService("dialog");
        this.ic = ic;
        this.fileRef = useRef("file");
        this.state = useState({
            loading: true, failed: false, d: null, busy: false,
            upload: { name: "", language: "any", file: null },
            limits: { person: 0, company: 0 },
            // PA1: the questions people asked, without names
            q: { which: "not_answered", rows: [], loading: false },
        });
        onWillStart(async () => {
            await this.load();
            await this.loadQuestions();
        });
    }

    async loadQuestions(which) {
        const q = this.state.q;
        if (which) { q.which = which; }
        if (!this.state.d || !this.state.d.questions_shown) { q.rows = []; return; }
        q.loading = true;
        try {
            q.rows = await this.orm.call(MODEL, "get_questions", [q.which]);
        } catch (e) {
            console.warn("pb_me_payai: could not read the questions", e);
            q.rows = [];
        } finally {
            q.loading = false;
        }
    }

    get downloadUrl() {
        const d = this.state.d;
        return `/pb_me_payai/questions.xlsx?company_id=${d.company_id}&which=${this.state.q.which}`;
    }

    take(d) {
        this.state.d = d;
        this.state.limits = { person: d.person_day, company: d.company_day };
    }

    async load() {
        try {
            this.take(await this.orm.call(MODEL, "get_desk", []));
            this.state.failed = false;
        } catch (e) {
            console.warn("pb_me_payai: could not read the policies desk", e);
            this.state.failed = true;
        } finally {
            this.state.loading = false;
        }
    }

    async run(method, args, ok) {
        if (this.state.busy) { return null; }
        this.state.busy = true;
        try {
            const d = await this.orm.call(MODEL, method, args);
            this.take(d);
            if (d.note) {
                this.notif.add(d.note, { type: d.documents.length ? "success" : "info" });
            } else if (ok) {
                this.notif.add(ok, { type: "success" });
            }
            return d;
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not go through."), { type: "danger" });
            return null;
        } finally {
            this.state.busy = false;
        }
    }

    toggleOn() {
        const on = !this.state.d.on;
        return this.run("set_switch", [on], on ? _t("Switched on for employees.") : _t("Switched off for employees."));
    }

    onLimit(key, ev) { this.state.limits[key] = ev.target.value; }

    saveLimits() {
        return this.run("set_limits", [this.state.limits.person, this.state.limits.company], _t("Daily limits saved."));
    }

    onPick(ev) {
        const file = ev.target.files && ev.target.files[0];
        this.state.upload.file = file || null;
        if (file && !this.state.upload.name) {
            this.state.upload.name = file.name.replace(/\.[^.]+$/, "");
        }
    }

    onName(ev) { this.state.upload.name = ev.target.value; }
    onLang(ev) { this.state.upload.language = ev.target.value; }

    async upload() {
        const up = this.state.upload;
        if (!up.file) {
            this.notif.add(_t("Choose a file first."), { type: "warning" });
            return;
        }
        if (up.file.size > MAX_BYTES) {
            this.notif.add(_t("That file is bigger than 10 MB. Upload a smaller one, or split it."), { type: "warning" });
            return;
        }
        const data = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result).split(",")[1] || "");
            reader.onerror = () => reject(reader.error);
            reader.readAsDataURL(up.file);
        });
        const d = await this.run("upload", [up.name, up.file.name, data, up.language]);
        if (d) {
            this.state.upload = { name: "", language: "any", file: null };
            if (this.fileRef.el) { this.fileRef.el.value = ""; }
        }
    }

    publish(doc) {
        return this.run("set_published", [doc.id, !doc.published],
            doc.published ? _t("Employees no longer ask about it.") : _t("Published. Employees can ask about it."));
    }

    remove(doc) {
        if (!window.confirm(_t("Remove “%s”? Employees can no longer ask about it.", doc.name))) { return; }
        return this.run("remove", [doc.id], _t("Removed."));
    }

    get liveWords() {
        const d = this.state.d;
        if (!d.ready) { return _t("Not available yet: this company has no AI account set up."); }
        if (!d.on) { return _t("Off. Employees do not see it."); }
        if (!d.published) { return _t("On, but no policy is published yet. Employees do not see it until one is."); }
        return _t("On. Employees see Company policies on their own pages.");
    }

    get isLive() {
        const d = this.state.d;
        return d.ready && d.on && d.published > 0;
    }
}

registry.category(HOME_LENSES).add("policies", {
    key: "policies",
    icon: "bookOpen",
    label: _t("Policies"),
    Component: PbPolicyDesk,
    groups: ["hr.group_hr_user"],
    probe: { model: MODEL, method: "can_open" },
}, { sequence: 16 });
