/** @odoo-module **/
/**
 * "Log a toolbox talk" (LEARNING L4) — one drawer, used by Courses › Sessions
 * (the training team, anybody) and by My learning's team block (a supervisor,
 * for the people under them).
 *
 * Topic (a classroom course, or a new topic typed on the spot), when (default
 * now), where, minutes (default 15), who was there (accent-blind search,
 * ticked list), an optional photo of the paper sign-in sheet (the back camera
 * on a phone). Saving makes a closed toolbox session with everybody marked as
 * attended, in one go — `pb.training.act('log_toolbox')`, which checks who may
 * include whom.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const MAX_PHOTO = 5 * 1024 * 1024;

/** "2026-10-22T09:30" (the browser's own clock) for a datetime-local box. */
export function toLocalInput(date) {
    const pad = (n) => String(n).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/** A datetime-local value → the server's UTC "YYYY-MM-DD HH:MM:SS". */
export function toServerUtc(value) {
    if (!value) { return ""; }
    const d = new Date(value);
    if (isNaN(d.getTime())) { return ""; }
    return d.toISOString().slice(0, 19).replace("T", " ");
}

/** The server's UTC "YYYY-MM-DD HH:MM:SS" → a datetime-local value. */
export function fromServerUtc(value) {
    if (!value) { return ""; }
    const d = new Date(value.replace(" ", "T") + "Z");
    return isNaN(d.getTime()) ? "" : toLocalInput(d);
}

export class PbToolboxDrawer extends Component {
    static template = "pb_training.PbToolboxDrawer";
    static props = {
        onClose: { type: Function },
        onSaved: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.state = useState({
            loaded: false,
            allowed: true,
            isTeam: false,
            courses: [],
            mode: "course",
            form: {
                channel_id: 0, new_course: "",
                start: toLocalInput(new Date(Date.now() - 15 * 60000)),
                place: "", minutes: 15, notes: "",
                photo: "", photo_name: "",
            },
            picked: [],
            term: "",
            people: [],
            saving: false,
        });
        onWillStart(() => this.load());
    }

    ic(n, s = 16) { return ic(n, s); }

    async load() {
        try {
            const d = await this.orm.call("pb.training", "toolbox_lists", []);
            this.state.allowed = d.allowed !== false;
            this.state.isTeam = !!d.is_team;
            this.state.courses = d.courses || [];
            if (!this.state.courses.length) { this.state.mode = "new"; }
            if (this.state.allowed) { await this.search(); }
        } catch (e) {
            console.warn("pb_training: the toolbox talk lists could not be read", e);
            this.state.allowed = false;
        } finally {
            this.state.loaded = true;
        }
    }

    async search() {
        try {
            this.state.people = await this.orm.call("pb.training", "toolbox_people", [this.state.term]);
        } catch (e) {
            console.warn("pb_training: the people search failed", e);
            this.state.people = [];
        }
    }

    onTerm(ev) {
        this.state.term = ev.target.value;
        clearTimeout(this._timer);
        this._timer = setTimeout(() => this.search(), 220);
    }

    isPicked(p) { return this.state.picked.some((x) => x.id === p.id); }

    toggle(p) {
        const list = this.state.picked;
        const at = list.findIndex((x) => x.id === p.id);
        if (at >= 0) { list.splice(at, 1); } else { list.push({ id: p.id, name: p.name }); }
    }

    pickAllShown() {
        for (const p of this.state.people) {
            if (!this.isPicked(p)) { this.state.picked.push({ id: p.id, name: p.name }); }
        }
    }

    setField(field, ev, kind = "text") {
        let value = ev.target.value;
        if (kind === "int") { value = Number(value) || 0; }
        this.state.form[field] = value;
    }

    setMode(mode) { this.state.mode = mode; }

    onPhoto(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file) { return; }
        if (file.size > MAX_PHOTO) {
            this.notif.add(_t("The photo is bigger than 5 MB."), { type: "danger" });
            ev.target.value = "";
            return;
        }
        const reader = new FileReader();
        reader.onload = () => {
            const text = String(reader.result || "");
            this.state.form.photo = text.includes(",") ? text.split(",")[1] : text;
            this.state.form.photo_name = file.name;
        };
        reader.readAsDataURL(file);
    }

    clearPhoto() { this.state.form.photo = ""; this.state.form.photo_name = ""; }

    get hint() {
        const f = this.state.form;
        if (this.state.mode === "course" && !f.channel_id) { return _t("Pick the topic."); }
        if (this.state.mode === "new" && !f.new_course.trim()) { return _t("Name the new topic."); }
        if (!this.state.picked.length) { return _t("Tick who was there."); }
        return "";
    }

    get canSave() { return !this.hint && !this.state.saving; }

    get pickedWords() {
        const n = this.state.picked.length;
        return n === 1 ? _t("1 person ticked") : _t("%s people ticked", n);
    }

    async save() {
        if (!this.canSave) { return; }
        const f = this.state.form;
        const payload = {
            channel_id: this.state.mode === "course" ? f.channel_id : 0,
            new_course: this.state.mode === "new" ? f.new_course : "",
            start: toServerUtc(f.start),
            place: f.place,
            minutes: f.minutes || 15,
            notes: f.notes,
            employee_ids: this.state.picked.map((p) => p.id),
            photo: f.photo || false,
            photo_name: f.photo_name || "",
        };
        this.state.saving = true;
        try {
            const res = await this.orm.call("pb.training", "act", ["log_toolbox", payload]);
            this.notif.add((res && res.message) || _t("Saved."), { type: "success" });
            if (this.props.onSaved) { await this.props.onSaved(res); }
            this.props.onClose();
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not work."), { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }
}
