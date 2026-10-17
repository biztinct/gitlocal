/** @odoo-module **/
/**
 * LEARN v3 — Learn > Settings: every learning switch on one card.
 *
 * Five features were built and shipped off, and four of them had no screen at
 * all. This lens is that screen. It writes nothing of its own: each toggle is
 * one call to `learn.settings.set_switch`, which re-asks for administrator
 * rights, writes the parameter the feature already reads, and returns the
 * whole card re-read — so what is drawn is always what the server holds.
 *
 * The lens is gated to administrators in learn_hub.js. The server gate is the
 * real one; this component still draws a plain "only an administrator" line if
 * it is ever mounted for someone else, rather than a card whose switches fail.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

import { RT, T } from "../engine/runtime";
import { loadContent } from "../content/content_loader";

/* LEARNREV P3 — the one preference this page keeps per device (the Learning
   page's header lost its "Reduce motion" button, G13). Same key the Journey
   and the helper read; the system's own reduced-motion setting is honoured
   whatever this says (runtime.js `reduced()`). */
const LOCAL_PREFS = "pbLearnPrefs";
/* Switches the Learning page no longer draws anything for (owner decision
   2026-10-17: no streaks, no badge levels). Still served, never offered. */
const HIDDEN_SWITCHES = new Set(["skill_tree"]);

function readMotion() {
    try {
        return (JSON.parse(window.localStorage.getItem(LOCAL_PREFS) || "{}") || {}).motion === "reduced";
    } catch {
        return false;
    }
}

/* LEARNREV P5a (S4) — the words of the "What people asked and rated" card.
   Written here as pairs, not as content-plane keys: P5a does not regenerate
   the content plane (P5b owns it); P5b's Vietnamese pass reviews these. */
const FB = {
    title: { en: "What people asked and rated", vi: "Mọi người đã hỏi và đánh giá gì" },
    lead: {
        en: "Which help people found useful, and what they searched for and did not find. Counts only: no names, no pay figures.",
        vi: "Phần trợ giúp nào hữu ích, và mọi người đã tìm gì mà không thấy. Chỉ có con số: không có tên, không có số liệu lương.",
    },
    period: { en: "Period", vi: "Khoảng thời gian" },
    d7: { en: "Last 7 days", vi: "7 ngày qua" },
    d30: { en: "Last 30 days", vi: "30 ngày qua" },
    d90: { en: "Last 90 days", vi: "90 ngày qua" },
    export: { en: "Download as CSV", vi: "Tải xuống dạng CSV" },
    loading: { en: "Reading the numbers…", vi: "Đang đọc số liệu…" },
    failed: {
        en: "The numbers could not be read. Try again in a moment.",
        vi: "Không đọc được số liệu. Hãy thử lại sau ít phút.",
    },
    retry: { en: "Try again", vi: "Thử lại" },
    helpful: { en: "Marked helpful", vi: "Được đánh dấu hữu ích" },
    notHelpful: { en: "Marked not helpful", vi: "Được đánh dấu chưa hữu ích" },
    noAnswer: { en: "Helper had no answer", vi: "Trợ lý không có câu trả lời" },
    noResult: { en: "Searches with no result", vi: "Lượt tìm không có kết quả" },
    ratingsTitle: { en: "Ratings by screen", vi: "Đánh giá theo màn hình" },
    ratingsEmpty: {
        en: "No ratings yet. They appear when someone presses a thumb on a field card.",
        vi: "Chưa có đánh giá nào. Chúng xuất hiện khi ai đó bấm ngón tay cái trên thẻ của một trường.",
    },
    missTitle: { en: "Questions the helper could not answer", vi: "Câu hỏi trợ lý chưa trả lời được" },
    missEmpty: {
        en: "None in this period: every question found an answer.",
        vi: "Không có trong khoảng này: mọi câu hỏi đều có câu trả lời.",
    },
    searchTitle: { en: "Top searches with no result", vi: "Các lượt tìm không có kết quả nhiều nhất" },
    searchEmpty: {
        en: "None in this period: every search found something.",
        vi: "Không có trong khoảng này: mọi lượt tìm đều có kết quả.",
    },
    searchHidden: {
        en: "Search words are not kept, so only their counts show. Switch on keeping questions above to read the words.",
        vi: "Từ khóa tìm kiếm không được lưu, nên chỉ hiện số lượt. Hãy bật việc lưu câu hỏi ở trên để đọc các từ khóa.",
    },
    searchHiddenOne: { en: "Words not kept", vi: "Từ khóa không được lưu" },
    times: { en: "×", vi: "×" },
    fieldsShow: { en: "Show the fields", vi: "Xem các trường" },
    fieldsHide: { en: "Hide the fields", vi: "Ẩn các trường" },
    showMore: { en: "Show all screens", vi: "Xem mọi màn hình" },
    showLess: { en: "Show fewer", vi: "Thu gọn" },
    noScreen: { en: "Not tied to a screen", vi: "Không gắn với màn hình nào" },
};
const SHOWN = 6;

/* The words for each switch. Keys into the content plane's chrome, so the
   card follows the same English / Vietnamese preference as the helper. */
const COPY = {
    next_best: { title: "swNextTitle", body: "swNextBody", icon: "compass" },
    skill_tree: { title: "swSkillTitle", body: "swSkillBody", icon: "award" },
    compose: { title: "swComposeTitle", body: "swComposeBody", icon: "sparkles",
               leaves: "swComposeLeaves", notReady: "swNoProvider" },
    voice: { title: "swVoiceTitle", body: "swVoiceBody", icon: "message-circle",
             leaves: "swVoiceLeaves", notReady: "swNoSpeech" },
    collect: { title: "swCollectTitle", body: "swCollectBody", icon: "lightbulb" },
    // LEARNREV P2
    guide: { title: "swGuideTitle", body: "swGuideBody", icon: "book-open" },
};

export class LearnSettings extends Component {
    static template = "pb_learn.LearnSettings";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            allowed: false,
            switches: [],
            busy: "",          // key of the switch being saved
            saved: "",         // key of the switch just saved
            failed: "",        // key of the switch that failed to save
            motion: readMotion(),
            // LEARNREV P5a (S4): the feedback card.
            fb: { loading: true, failed: false, days: 30, data: null, open: {}, all: false },
        });
        onWillStart(async () => {
            try {
                const content = await loadContent();
                if (!Object.keys(RT.chrome || {}).length) {
                    RT.chrome = content.chrome || {};
                }
                this.state.allowed = await this.orm.call("learn.settings", "can_manage", []);
                if (this.state.allowed) {
                    this.state.switches = await this.orm.call("learn.settings", "get_switches", []);
                    this.loadFeedback();
                }
            } catch {
                this.state.allowed = false;
            } finally {
                this.state.loading = false;
            }
        });
    }

    t(key) {
        return T(key);
    }

    /** One of the feedback card's words, in the page's language. */
    f(key) {
        const p = FB[key] || {};
        return p[RT.lang] || p.en || key;
    }

    /** Read the report for the chosen period. A failure is a sentence and a
     *  Try again button, never a blank card. */
    async loadFeedback(days) {
        const fb = this.state.fb;
        if (days) {
            fb.days = days;
        }
        fb.loading = true;
        fb.failed = false;
        try {
            fb.data = await this.orm.call("learn.feedback", "report", [fb.days, RT.lang]);
        } catch {
            fb.failed = true;
        } finally {
            fb.loading = false;
        }
    }

    onPeriod(ev) {
        this.loadFeedback(parseInt(ev.target.value, 10) || 30);
    }

    toggleFields(screen) {
        this.state.fb.open[screen] = !this.state.fb.open[screen];
    }

    screenRows() {
        const rows = (this.state.fb.data && this.state.fb.data.thumbs) || [];
        return this.state.fb.all ? rows : rows.slice(0, SHOWN);
    }

    moreScreens() {
        const rows = (this.state.fb.data && this.state.fb.data.thumbs) || [];
        return rows.length > SHOWN;
    }

    /** Share of a row's ratings that were "not helpful", as a bar width. */
    downShare(row) {
        const total = row.up + row.down;
        return total ? Math.round((100 * row.down) / total) : 0;
    }

    phraseLabel(row) {
        return row.phrase || `${this.f("searchHiddenOne")} · ${row.id.slice(2, 6)}`;
    }

    /** Download the same numbers as one CSV file. The server builds the text
     *  (and guards every cell against being run as a formula); this only
     *  hands it to the browser. A BOM keeps Vietnamese letters right in Excel. */
    async exportCsv() {
        try {
            const r = await this.orm.call("learn.feedback", "export_csv",
                [this.state.fb.days, RT.lang]);
            const blob = new Blob(["﻿" + r.csv], { type: "text/csv;charset=utf-8" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = r.filename;
            document.body.appendChild(a);
            a.click();
            a.remove();
            setTimeout(() => URL.revokeObjectURL(url), 2000);
        } catch {
            this.state.fb.failed = true;
        }
    }

    /** "Reduce motion" on this device: lessons, walkthroughs and the helper
     *  move less. Written straight to the browser, nothing to the server. */
    toggleMotion() {
        const on = !this.state.motion;
        this.state.motion = on;
        RT.motion = on ? "reduced" : "auto";
        try {
            const p = JSON.parse(window.localStorage.getItem(LOCAL_PREFS) || "{}") || {};
            p.motion = RT.motion;
            window.localStorage.setItem(LOCAL_PREFS, JSON.stringify(p));
        } catch {
            // A locked-down profile keeps the choice for this page only.
        }
    }

    rows() {
        return this.state.switches.filter((s) => !HIDDEN_SWITCHES.has(s.key)).map((s) => {
            const c = COPY[s.key] || {};
            return {
                ...s,
                title: T(c.title),
                body: T(c.body),
                icon: c.icon || "info",
                note: s.leaves && c.leaves ? T(c.leaves) : T("swStays"),
                warn: !s.ready && c.notReady ? T(c.notReady) : "",
            };
        });
    }

    async toggle(row) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = row.key;
        this.state.saved = "";
        this.state.failed = "";
        try {
            this.state.switches = await this.orm.call(
                "learn.settings", "set_switch", [row.key, !row.on]);
            this.state.saved = row.key;
            setTimeout(() => {
                if (this.state.saved === row.key) {
                    this.state.saved = "";
                }
            }, 2200);
        } catch {
            this.state.failed = row.key;
        } finally {
            this.state.busy = "";
        }
    }
}
