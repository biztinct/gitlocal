/** @odoo-module **/
/**
 * Learning › Courses › New course › "Draft it with PayAI from a document"
 * (LEARNING L7, owner decision LD9).
 *
 * HERO MOMENT: drop a procedure in, press "Draft the course", and a few
 * seconds later the course drawer opens on a DRAFT — outline, short lessons,
 * a ten-question quiz — with "Drafted by PayAI from <file>. Read every lesson
 * before you publish." on top. Nothing is published.
 *
 * Bounded upload: PDF, Word or text, 10 MB at most (checked here before a
 * byte is sent, and again on the server). With no PayAI provider set up the
 * card says so and offers nothing to press. A document PayAI's chat picked
 * arrives pre-filled (`startAttachment`): the person only chooses the
 * language and presses the button.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { NEW_COURSE_WAYS } from "@pb_training/js/training_board";

const MAX_BYTES = 10 * 1024 * 1024;
const ACCEPT = ".pdf,.docx,.txt,application/pdf,text/plain,"
    + "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

export class PbDraftWithPayAI extends Component {
    static template = "pb_training_payai.PbDraftWithPayAI";
    static props = {
        startAttachment: { type: Number, optional: true },
        onMade: { type: Function, optional: true },
        onClose: { type: Function, optional: true },
        "*": true,
    };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.accept = ACCEPT;
        this.state = useState({
            loaded: false, ready: false, notReady: "", languages: [],
            language: "en", file: null, fileName: "", attachment: null,
            problem: "", busy: false,
        });
        onWillStart(() => this.load());
    }

    ic(n, s = 16) { return ic(n, s); }

    async load() {
        try {
            const setup = await this.orm.call("pb.training", "draft_setup", []);
            this.state.ready = !!setup.ready;
            this.state.notReady = setup.not_ready_words || "";
            this.state.languages = setup.languages || [];
            this.state.language = setup.language || "en";
            if (this.props.startAttachment) {
                const att = await this.orm.call("pb.training", "draft_attachment_info",
                                                [this.props.startAttachment]);
                if (att && att.id) { this.state.attachment = att; }
            }
        } catch (e) {
            this.state.ready = false;
            this.state.notReady = (e && e.data && e.data.message) || _t("That did not load. Try again in a moment.");
        } finally {
            this.state.loaded = true;
        }
    }

    get fileLabel() {
        if (this.state.attachment) { return this.state.attachment.name; }
        return this.state.fileName;
    }

    get canDraft() {
        return this.state.ready && !this.state.busy && (this.state.file || this.state.attachment);
    }

    pickLanguage(key) { this.state.language = key; }

    /** A CHANGE handler: the file is checked here before anything is sent. */
    onFile(ev) {
        const file = ev.target.files && ev.target.files[0];
        this.state.problem = "";
        this.state.attachment = null;
        if (!file) { this.state.file = null; this.state.fileName = ""; return; }
        if (file.size > MAX_BYTES) {
            this.state.file = null;
            this.state.fileName = "";
            this.state.problem = _t("That file is larger than 10 MB. Upload a shorter document, or the part of it the course is about.");
            ev.target.value = "";
            return;
        }
        if (!/\.(pdf|docx|txt)$/i.test(file.name || "")) {
            this.state.file = null;
            this.state.fileName = "";
            this.state.problem = _t("PayAI can draft a course from a PDF, a Word file or a text file. Save it as one of those and upload it again.");
            ev.target.value = "";
            return;
        }
        this.state.file = file;
        this.state.fileName = file.name;
    }

    readBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
                const out = String(reader.result || "");
                resolve(out.slice(out.indexOf(",") + 1));
            };
            reader.onerror = () => reject(reader.error);
            reader.readAsDataURL(file);
        });
    }

    /** A CLICK handler: one call; the server checks everything again. */
    async draft() {
        if (!this.canDraft) { return; }
        this.state.busy = true;
        this.state.problem = "";
        try {
            let res;
            if (this.state.attachment) {
                res = await this.orm.call("pb.training", "draft_course",
                                          [this.state.attachment.id, this.state.language]);
            } else {
                const data = await this.readBase64(this.state.file);
                res = await this.orm.call("pb.training", "draft_upload",
                                          [this.state.fileName, data, this.state.language]);
            }
            this.notif.add(res.message || _t("Drafted."), { type: "success" });
            if (this.props.onMade) { await this.props.onMade(res.channel_id); }
        } catch (e) {
            this.state.problem = (e && e.data && e.data.message)
                || _t("PayAI could not draft a course just now. Try again in a minute, or start a blank course.");
        } finally {
            this.state.busy = false;
        }
    }
}

registry.category(NEW_COURSE_WAYS).add("payai", {
    key: "payai",
    Component: PbDraftWithPayAI,
}, { sequence: 20 });
