/** @odoo-module **/

import { Component, useState, useRef, useEffect, onMounted, onWillUnmount, onWillUpdateProps, toRaw } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { ChartRenderer } from "../chart_renderer/chart_renderer";
// LEARN REFRESH step 1 — where the user is, as the hubs publish it, and the
// hub door the "Show me" hand-off now goes through (both via pb_learn's
// dependency on pb_hub).
import { hubPlace } from "@pb_hub/js/hub_place";
import { openHub } from "@pb_hub/js/hub_nav";

// LEARNOS Phase 6. A ceiling on one held press, and where the read-aloud
// preference is remembered. Both are browser-side: the recording ceiling is a
// courtesy to the person holding the button, and the server's own gates are
// what decide whether any of this is offered at all.
const MAX_RECORDING_SECONDS = 60;
const TTS_PREF = "payaiReadAloud";

/* ONECHAT OC2 — the marks only Vietnamese text carries. Read-aloud picks its
   voice from the text it is about to read, not from the page (§6.5): a
   Vietnamese answer is read by a Vietnamese voice whatever the pill says. */
const VI_MARKS = /[ăâđêôơưàáạảãèéẹẻẽìíịỉĩòóọỏõùúụủũỳýỵỷỹ]/i;

/* ONECHAT OC3 — the microphone's timings and thresholds (handover §6.2). */
const HOLD_MS = 400;              // a press held longer stops on release
const MIN_RECORDING_MS = 700;     // shorter than this is never uploaded
const SILENT_LEVEL = 0.02;        // RMS the loudest moment must pass
const METER_MS = 80;              // the level meter reads ~12 times a second
const VOICES_WAIT_MS = 1000;      // how long to wait for the device's voices
const SPEECH_CAP = 600;           // characters read aloud, at most

/* What this page's speech has already done: primed once inside a tap (iOS),
   the "no Vietnamese voice" notice shown once. */
const SPEECH = { primed: false, noViShown: false };

/** The recording format this browser can make, best first, or null: then
 *  the microphone is not drawn ("This browser cannot record here"). WebM/Opus
 *  is Chrome and Firefox; MP4 is Safari and iOS. */
export function pickRecordingType() {
    const MR = typeof globalThis !== "undefined" ? globalThis.MediaRecorder : undefined;
    const media = typeof navigator !== "undefined" && navigator.mediaDevices;
    if (!MR || !media || typeof media.getUserMedia !== "function"
            || typeof MR.isTypeSupported !== "function") {
        return null;
    }
    for (const type of ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"]) {
        try {
            if (MR.isTypeSupported(type)) {
                return type;
            }
        } catch {
            // try the next one
        }
    }
    return null;
}

/** Lower case, no marks, no punctuation, one space. */
function foldWords(text) {
    return String(text || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "")
        .replace(/đ/g, "d").replace(/Đ/g, "d").toLowerCase()
        .replace(/[^a-z0-9]+/g, " ").trim();
}

/* What the speech service writes when it heard nothing (folded): the closing
   lines of the videos it learned from. Never a real question. */
const PHANTOMS = [
    /^(thank you|thanks) (so much )?for watching( and listening)?$/,
    /^(please )?(like (and|&) )?subscribe( to (the|my|our) channel)?$/,
    /^subtitles? (by|from)\b/,
    /^(hay )?(dang ky|subscribe) (cho )?kenh\b/,
    /^hay subscribe cho kenh\b/,
    /^cam on (cac ban )?(da )?(xem|theo doi)( video)?$/,
];

/** The hint's terms, folded, as word lists ("pay run" → ["pay", "run"]). */
function hintTerms(hint) {
    return String(hint || "").split(",").map((t) => foldWords(t).split(" ").filter(Boolean))
        .filter((t) => t.length);
}

/** True when a transcript is not something a person said: one of the
 *  service's filler lines, or the hint it was given read back (it echoes the
 *  hint on silence — ledger OC14). An echo is WHOLE hint terms: either
 *  nothing but hint terms (three or more), or five or more of them in the
 *  hint's own order with nothing in between. A question that merely names a
 *  few product terms side by side ("tính tăng ca BHXH BHYT thế nào", "how is
 *  overtime BHXH BHYT BHTN worked out") is a real question (ledger OC57). */
export function isPhantomTranscript(text, vocab) {
    const said = foldWords(text);
    if (!said) {
        return true;
    }
    if (PHANTOMS.some((re) => re.test(said))) {
        return true;
    }
    const words = said.split(" ");
    for (const hint of Object.values(vocab || {})) {
        const terms = hintTerms(hint);
        if (!terms.length) {
            continue;
        }
        let found = 0;
        let other = 0;
        let run = 0;
        let longest = 0;
        let last = -2;
        for (let i = 0; i < words.length;) {
            // the longest hint term starting here
            let hit = -1;
            let size = 0;
            terms.forEach((term, k) => {
                if (term.length > size && term.every((w, n) => words[i + n] === w)) {
                    hit = k;
                    size = term.length;
                }
            });
            if (hit < 0) {
                other += 1;
                run = 0;
                last = -2;
                i += 1;
                continue;
            }
            found += 1;
            run = hit === last + 1 ? run + 1 : 1;
            longest = Math.max(longest, run);
            last = hit;
            i += size;
        }
        if ((other === 0 && found >= 3) || longest >= 5) {
            return true;
        }
    }
    return false;
}

/* ONECHAT — NO AMOUNT IS EVER SPOKEN (owner decision Q2), in any currency or
   format, and a HEAD COUNT or a DATE is still read ("1,000 people",
   "1.000 người", "June 2026", "tháng 6", "15/6").
   One matcher finds every number together with what can sit around it:
     a currency sign or code before or after it, glued or spaced, a code in
     any case ("₫", "VND", "vnd950", "USD1,200", "đ", "RM200", "S$950",
     "MYR 950", "950 THB", "K950,000");
     a scale word after it, with or without a space ("18.6 bn", "65.8 tỷ",
     "2 triệu", "5tr", "500k", "$1.2m", "12.5 million");
     the number itself, grouped in threes by "," "." or a space ("1,234,567",
     "500.000", "1 000 000") or not.
   Then, by context (`isAmount`): a sign or a scale word → money; a count
   word after it ("people", "payslips", "runs", "checks", "người", "đợt"),
   a percent sign, or a date shape ("15/6", "2026-06-15") → read; decimals
   ("25.75") → money; a year (1900–2099) → read; a plain number right after
   an id label ("run 681", "payslip #1234", "employee ID 00451", "mã 4500")
   → read, unless a money word stands before the label ("each employee
   950"); any other number of three digits or more ("950", "4500") → money;
   one or two digits → read.
   Values the plan card marks as money (its `value` / `figures` rows) are
   withheld word for word first (`opts.money`). Case matters for the short
   signs — "RM" and "Rp" are signs, "perform 200 checks" is not (ledger
   OC58). No look-behind (OC49): the character before a number is captured. */
const NOT_WORD = "(?![A-Za-z0-9À-ỹ])";
/* A code may be glued to its digits ("USD1,200"); only a LETTER after it
   makes it part of a longer word ("usda", "VNDirect"). */
const NOT_LETTER = "(?![A-Za-zÀ-ỹ])";
/** A word in any letter case, as a character class per letter. */
function anyCase(word) {
    return Array.from(word).map((ch) => {
        const lo = ch.toLowerCase();
        const up = ch.toUpperCase();
        return lo === up ? ch.replace(/[.$]/g, "\\$&") : `[${lo}${up}]`;
    }).join("");
}
const CODES = ["VND", "VNĐ", "USD", "SGD", "MYR", "THB", "INR", "IDR", "KHR", "EUR", "GBP",
               "AUD", "NZD", "HKD", "JPY", "CNY", "LAK", "MMK", "BND", "PHP", "CHF", "CAD"];
const MONEY_SIGN = "(?:[A-Z]{1,2}\\$|RM|Rp|Rs\\.?|S\\/\\.?|Ks?(?=\\d)|[$€£₫฿₹៛₱¥₩₭]|đ|(?:"
    + CODES.map(anyCase).join("|") + ")" + NOT_LETTER + ")";
/* After the number a currency's own word counts as a sign too ("500 đồng",
   "50 dollars", "20 đô la"). */
const MONEY_SIGN_AFTER = "(?:" + MONEY_SIGN + "|(?:"
    + ["đồng", "dong", "đô la", "đô", "dollars", "dollar", "bucks", "euros", "euro", "pounds",
       "cents", "cent", "rupees", "rupee", "rupiah", "ringgit", "baht", "riels", "riel", "kyats",
       "kyat", "kip", "pesos", "peso", "yen", "yuan"].map(anyCase).join("|") + ")" + NOT_WORD + ")";
/* Scale words. The one-letter ones only straight after the digits ("500k",
   "1.2m"); the words with or without a space ("18.6 bn", "5tr", "2 triệu"). */
const SCALE_TIGHT = "(?:[kKmM]" + NOT_WORD + ")";
const SCALE_WORD = "(?:(?:" + ["bn", "billion", "billions", "million", "millions", "mn", "mil",
    "thousand", "thousands", "lakh", "lakhs", "crore", "crores", "triệu", "trieu", "tr",
    "tỷ", "tỉ", "ty", "nghìn", "ngàn", "nghin", "ngan"].map(anyCase).join("|") + ")" + NOT_WORD + ")";
const AMOUNT_NUM = "(?:\\d{1,3}(?:[.,]\\d{3})+(?:[.,]\\d+)?|\\d{1,3}(?: \\d{3})+|\\d+(?:[.,]\\d+)?)(?!\\d)";
/* The character before a number: start, or anything but a letter or digit —
   and a "," / "." only when no digit stands before it, so the tail of
   "12,000,000" is never matched on its own. */
const AMOUNT_RE = new RegExp("(^|[^A-Za-z0-9À-ỹ.,]|(?:^|[^0-9])[.,])"
    + "(?:(" + MONEY_SIGN + ")\\s?)?"
    + "(" + AMOUNT_NUM + ")"
    + "(" + SCALE_TIGHT + "?(?:\\s?" + SCALE_WORD + ")*)"
    + "(?:\\s?(" + MONEY_SIGN_AFTER + "))?"
    + NOT_WORD, "g");
/* What a count is counting: read, never withheld ("1,000 people", "3 runs",
   "200 checks", "12 phiếu lương"). One describing word may sit between
   ("40 more people", "5 đợt mới" is after, so not needed). */
const COUNT_NOUNS = ["people", "persons", "person", "employees", "employee", "staff", "workers",
    "worker", "members", "member", "payslips", "payslip", "heads", "runs", "run", "checks", "check",
    "items", "item", "requests", "request", "rows", "row", "lines", "line", "steps", "step",
    "days", "day", "hours", "hour", "minutes", "minute", "weeks", "week", "months", "month",
    "years", "year", "times", "errors", "error", "flags", "flag", "files", "file", "changes",
    "change", "approvals", "approval", "approvers", "approver", "lessons", "lesson", "questions",
    "question", "records", "record", "entries", "entry", "companies", "company", "departments",
    "department", "divisions", "division", "teams", "team", "schemes", "scheme", "components",
    "component", "slips", "slip",
    "người", "nhân viên", "nhân sự", "lao động", "phiếu lương", "phiếu", "đợt", "ngày", "giờ",
    "phút", "tuần", "tháng", "năm", "lần", "yêu cầu", "dòng", "bước", "mục", "công ty",
    "phòng ban", "bài học", "câu hỏi", "hồ sơ"];
const COUNT_RE = new RegExp("^\\s*(?:(?:" + ["more", "new", "active", "other", "extra", "open",
    "pending", "draft", "unpaid", "paid", "missing"].map(anyCase).join("|") + ")\\s+)?(?:"
    + COUNT_NOUNS.map(anyCase).join("|") + ")" + NOT_WORD);
const PERCENT_RE = new RegExp("^\\s?(?:%|" + ["percent", "per cent", "phần trăm"].map(anyCase).join("|")
    + NOT_WORD + ")");
/* What an id or a reference is called. The plain number straight after one
   is read ("run 681", "payslip #1234", "employee ID 00451", "room 305",
   "mã 4500", "đợt lương 681"), unless a money word stands just before the
   label ("each employee 950", "lương nhân viên 950", "pay to employee 950" —
   but "pay run 681" is a pay run). A grouped or decimal figure after a label
   stays money ("payslip 1,234"); only "version" takes dots ("version 19.0"). */
const ID_LABELS = ["phiếu lương", "đợt lương", "nhân viên", "payslip", "slip", "employee", "run",
    "id", "no.", "number", "code", "step", "version", "line", "row", "page", "room", "ext",
    "mã", "số", "đợt", "phiếu", "bước", "dòng", "trang", "phòng"];
const ID_LABEL_RE = new RegExp("(^|[^A-Za-z0-9À-ỹ])(" + ID_LABELS.map(anyCase).join("|")
    + ")\\.?\\s*[#:]?\\s*$");
const ID_HASH_RE = /#\s*$/;
const MONEY_WORDS = ["pay", "pays", "paid", "paying", "give", "gives", "gave", "giving", "grant",
    "grants", "each", "every", "per", "total", "totals", "cost", "costs", "bonus", "bonuses",
    "salary", "salaries", "wage", "wages", "allowance", "allowances", "net", "gross", "amount",
    "amounts", "owe", "owes", "owed", "charge", "charges", "fee", "fees", "price", "rate", "worth",
    "earn", "earns", "earned", "budget", "deduct", "deducts", "deduction", "refund", "transfer",
    "mỗi", "trả", "tổng", "thưởng", "tiền", "chi", "phí", "lương", "phụ cấp", "khấu trừ", "giá",
    "mức", "nhận", "chuyển"];
const MONEY_FILLERS = ["the", "a", "an", "this", "that", "his", "her", "their", "its", "to", "for",
    "of", "cho", "của"];
const MONEY_BEFORE_RE = new RegExp("(?:^|[^A-Za-z0-9À-ỹ])(" + MONEY_WORDS.map(anyCase).join("|")
    + ")((?:\\s+(?:" + MONEY_FILLERS.map(anyCase).join("|") + "))*)\\s*$");

/** The id label the text before a number ends with, when it is not money
 *  context: "run", "#", "mã" …; else null. */
function idLabelBefore(head) {
    let start;
    let label;
    const m = ID_LABEL_RE.exec(head);
    if (m) {
        start = m.index + m[1].length;
        label = m[2].toLowerCase();
    } else if (ID_HASH_RE.test(head)) {
        start = head.lastIndexOf("#");
        label = "#";
    } else {
        return null;
    }
    const money = MONEY_BEFORE_RE.exec(head.slice(0, start));
    if (money) {
        // "pay run 681", "pay slip 1234": the run, not a payment.
        const payRun = /^pays?$/i.test(money[1]) && !money[2] && (label === "run" || label === "slip");
        if (!payRun) {
            return null;
        }
    }
    return label;
}

/** True when a number found by AMOUNT_RE is money, not a count, a date, a
 *  year or an id. `before` is the text before the number's own lead
 *  character. */
function isAmount(lead, sign, num, scale, signAfter, rest, before) {
    if (sign || signAfter) {
        return true;
    }
    if (COUNT_RE.test(rest) || PERCENT_RE.test(rest)) {
        return false;
    }
    if (scale && scale.trim()) {
        return true;
    }
    // A date or a time: "15/6", "15/06/2026", "2026-06-15", "10:30",
    // "15.06.2026", "2026.06.15".
    if (/^[/:-]\d/.test(rest) || (/[/:-]$/.test(lead) && /\d$/.test(before))) {
        return false;
    }
    // A dotted date only with a real day, month and year — "1.50.000" (a
    // lakh written with dots) is not one.
    const dmy = /^(\d{1,2})\.(\d{1,2})$/.exec(num);
    const ymd = /^(?:19|20)\d\d\.(\d{1,2})$/.exec(num);
    const tail = /^\.(\d{1,4})(?!\d)/.exec(rest);
    const day = (d) => Number(d) >= 1 && Number(d) <= 31;
    const month = (m) => Number(m) >= 1 && Number(m) <= 12;
    if (tail && ((dmy && day(dmy[1]) && month(dmy[2]) && /^(?:\d{2}|(?:19|20)\d\d)$/.test(tail[1]))
                 || (ymd && month(ymd[1]) && tail[1].length <= 2 && day(tail[1])))) {
        return false;
    }
    const label = idLabelBefore(before + lead);
    // "version 19.0", "version 2.1"
    if (label === "version" && /^\d+(?:\.\d+)*$/.test(num)) {
        return false;
    }
    // grouped in threes ("1,000", "500.000", "1 000 000")
    if (/^\d{1,3}(?:[.,\s]\d{3})+/.test(num)) {
        return true;
    }
    // decimals ("25.75", "18,6")
    if (/[.,]/.test(num)) {
        return true;
    }
    // a year ("June 2026", "năm 2031")
    if (/^(?:19|20)\d\d$/.test(num)) {
        return false;
    }
    // an id after its label ("run 681", "employee ID 00451", "mã 4500")
    if (label && /^\d+$/.test(num)) {
        return false;
    }
    // any other bare number of three digits or more ("950", "4500")
    return num.length >= 3;
}

/** Withhold the values a plan card marks as money, word for word. */
function withholdMarked(text, money, word) {
    let out = text;
    for (const raw of money || []) {
        const v = String(raw || "").trim();
        if (!v || !/\d/.test(v)) {
            continue;
        }
        out = out.split(v).join(word);
    }
    return out;
}

/** The plan card's money rows (value / amount / figures) — what the server
 *  marks as an amount — as the strings shown on the card. */
export function moneyOfCard(card) {
    const rows = (card && Array.isArray(card.slots)) ? card.slots : [];
    return rows.filter((r) => r && ["value", "amount", "money", "figures"].includes(r.key))
        .map((r) => String(r.value_label || ""))
        .filter((v) => /\d/.test(v));
}

/** The words handed to the device's synthesiser (handover §6.5): markup and
 *  markdown out, the brand filter (never "Odoo" spoken — the same rewrite
 *  the screen uses when the debranding layer is installed), NO AMOUNTS
 *  (owner decision Q2), at most SPEECH_CAP characters, cut at a sentence. */
export function speechText(text, opts = {}) {
    let say = String(text || "")
        .replace(/<[^>]*>/g, " ")
        .replace(/&nbsp;/g, " ").replace(/&amp;/g, "&").replace(/&lt;/g, "<")
        .replace(/&gt;/g, ">").replace(/&quot;/g, "\u0022").replace(/&#39;/g, "'")
        // the answer's list bullets and "---" rules are not words
        .replace(/^[ \t]*(?:[-+•][ \t]+|([-*_])(?:[ \t]*\1){2,}[ \t]*$)/gm, " ")
        // markdown marks out: stars and backticks hug their words
        // ("**Dữ liệu lương**:" → "Dữ liệu lương:"); a "#" is kept before
        // digits ("payslip #1234")
        .replace(/[*\x60]+/g, "")
        .replace(/[_>|~]+|#+(?!\d)/g, " ");
    say = debrandSpoken(say, opts.brand);
    const word = opts.amount || "an amount shown on screen";
    say = say.replace(/\s+/g, " ");
    say = withholdMarked(say, opts.money, word);
    say = say.replace(AMOUNT_RE, (m, lead, sign, num, scale, signAfter, at, all) => (
        isAmount(lead, sign, num, scale, signAfter, all.slice(at + m.length), all.slice(0, at))
            ? `${lead}${word}` : m));
    // "20 triệu 500 nghìn" is ONE amount, said once.
    const said = word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    say = say.replace(new RegExp(`${said}(?:\\s+${said})+`, "g"), word);
    // The rest of an odd grouping goes with it ("1.50.000" → never ".000").
    say = say.replace(new RegExp(`${said}(?:[.,]\\d+)+`, "g"), word);
    say = say.trim();
    if (say.length > SPEECH_CAP) {
        const cut = say.slice(0, SPEECH_CAP);
        const end = Math.max(cut.lastIndexOf(". "), cut.lastIndexOf("? "), cut.lastIndexOf("! "));
        say = end > SPEECH_CAP / 2 ? cut.slice(0, end + 1) : cut;
    }
    return say;
}

/** The screen's own brand rewrite when the debranding layer is installed
 *  (looked up at run time, so this module never depends on it); else the
 *  vendor's name becomes the product's. */
function debrandSpoken(text, brand) {
    let out = String(text || "");
    try {
        const loader = globalThis.odoo && globalThis.odoo.loader;
        const mod = loader && loader.modules && loader.modules.get
            && loader.modules.get("@biz_debrand/js/biz_debrand_runtime");
        if (mod && typeof mod.debrandText === "function") {
            out = String(mod.debrandText(out));
        }
    } catch {
        // the fallback below still applies
    }
    return out.replace(/\bodoo\b/gi, brand || "Payobook");
}

/** A voice for `lang` ("vi-VN" / "en-US") from the device's list, or null. */
export function pickVoice(voices, lang) {
    const want = String(lang || "").toLowerCase().replace("_", "-");
    const base = want.split("-")[0];
    const norm = (v) => String((v && v.lang) || "").toLowerCase().replace("_", "-");
    const list = Array.from(voices || []);
    return list.find((v) => norm(v) === want)
        || list.find((v) => norm(v).split("-")[0] === base)
        || null;
}

/* The kinds of turn the one chat records as a content-free marker in the
   person's conversation (`rpc_note_turn`, ONECHAT OC1). Mirrors the server's
   NOTE_KINDS; a history row with one of them is drawn as a marker. */
export const NOTE_KINDS = ["guide", "composed", "explain", "practice", "choose", "miss",
                           "capability", "note", "smalltalk"];

/** A plain options object — never an event. `t-on-click="sendMessage"`
 *  hands the handler the click event, which must not be read as options. */
function isOpts(o) {
    return !!o && typeof o === "object" && Object.getPrototypeOf(o) === Object.prototype;
}

/** A history row the helper wrote (a marker), or null. */
export function markerOf(row) {
    const card = row && row.card;
    const kind = card && card.kind;
    if (row && (row.intent === "helper_note"
            || (kind && NOTE_KINDS.includes(kind) && !card.task_id && !card.actions))) {
        return {
            role: "assistant", kind: "marker", mkind: kind || "note",
            key: (card && card.key) || "", label: row.content || "",
            content: row.content || "", card: null, chart: null, insights: [],
            timestamp: row.timestamp || "",
        };
    }
    return null;
}

/* ONECHAT — PayAI's free-text answers arrive as light markdown ("**Home ›
   Approvals**", "1. **Dữ liệu lương**: …"). They are drawn from a TREE OF
   PLAIN STRINGS (`richBlocks`), never from HTML: the templates
   (pb_payroll_ai_insights.RichText) print every piece with t-esc, so nothing
   the model writes can become a tag, a link, an image or a script — "<img
   src=x onerror=…>" is shown as those characters. The whitelist:
     **bold**, *italic*, ***both***, `code`;
     numbered ("1." / "1)") and bulleted ("-", "*", "+", "•") lists, one
     indented level under an item, an indented line continuing an item;
     "#" headings drawn as a bold line; "---" between paragraphs;
     line breaks and blank-line paragraphs.
   Anything else ("5 * 3", a lone "**", "[text](url)") stays as written.
   Shape: [{kind: "p", lines}, {kind: "ol"|"ul", start, items: [{lines,
   subs: [{kind, start, items: [{lines}]}]}]}], a line = [{text, b, i,
   code}]. No look-behind (older Safari, OC49). */
const RICH_OL = /^([ \t]*)(\d{1,3})[.)][ \t]+(.*)$/;
const RICH_UL = /^([ \t]*)[-*+•][ \t]+(.*)$/;
const RICH_H = /^[ \t]{0,3}#{1,6}[ \t]+(.*?)[ \t]*#*[ \t]*$/;
const RICH_RULE = /^[ \t]*([-*_])(?:[ \t]*\1){2,}[ \t]*$/;
const RICH_CODE = /`([^`\n]+)`/g;
/* At one position: *** before ** before *; the inside never starts or ends
   with a space or a star. */
const RICH_EMPH = /\*\*\*([^\s*](?:[^*]*?[^\s*])?)\*\*\*|\*\*([^\s*](?:[\s\S]*?[^\s*])?)\*\*|\*([^\s*](?:[^*]*?[^\s*])?)\*/;
const RICH_WORD = /[A-Za-z0-9À-ỹ]/;
const RICH_CACHE = new Map();
const RICH_CACHE_MAX = 300;

function richPush(out, text, f) {
    if (!text) {
        return;
    }
    const last = out[out.length - 1];
    if (last && last.b === !!f.b && last.i === !!f.i && last.code === !!f.code) {
        last.text += text;
    } else {
        out.push({ text: String(text), b: !!f.b, i: !!f.i, code: !!f.code });
    }
}

function richEmph(out, s, f) {
    let rest = s;
    while (rest) {
        const m = RICH_EMPH.exec(rest);
        if (!m) {
            richPush(out, rest, f);
            return;
        }
        const end = m.index + m[0].length;
        // A single star inside a word ("Rate*Hours*1.5") is not italic.
        if (m[3] !== undefined && ((m.index > 0 && RICH_WORD.test(rest[m.index - 1]))
                                   || (end < rest.length && RICH_WORD.test(rest[end])))) {
            richPush(out, rest.slice(0, m.index + 1), f);
            rest = rest.slice(m.index + 1);
            continue;
        }
        richPush(out, rest.slice(0, m.index), f);
        if (m[1] !== undefined) {
            richPush(out, m[1], { ...f, b: true, i: true });
        } else if (m[2] !== undefined) {
            richEmph(out, m[2], { ...f, b: true });
        } else {
            richPush(out, m[3], { ...f, i: true });
        }
        rest = rest.slice(end);
    }
}

/** One line of text → its pieces, [{text, b, i, code}]. */
export function richInline(text, flags = {}) {
    const out = [];
    const s = String(text || "");
    let at = 0;
    RICH_CODE.lastIndex = 0;
    let m;
    while ((m = RICH_CODE.exec(s))) {
        richEmph(out, s.slice(at, m.index), flags);
        richPush(out, m[1], { ...flags, code: true });
        at = m.index + m[0].length;
    }
    richEmph(out, s.slice(at), flags);
    return out;
}

/** A PayAI answer → the block tree the RichText template draws. */
export function richBlocks(text) {
    const src = String(text || "").replace(/\r\n?/g, "\n");
    if (RICH_CACHE.has(src)) {
        return RICH_CACHE.get(src);
    }
    const blocks = [];
    let para = null;
    let list = null;
    const indentOf = (ws) => ws.replace(/\t/g, "    ").length;
    for (const raw of src.split("\n")) {
        if (!raw.trim() || RICH_RULE.test(raw)) {
            para = null;
            list = null;
            continue;
        }
        const ol = RICH_OL.exec(raw);
        const ul = !ol && RICH_UL.exec(raw);
        if (ol || ul) {
            const kind = ol ? "ol" : "ul";
            const start = ol ? Number(ol[2]) : 1;
            const item = { lines: [richInline(ol ? ol[3] : ul[2])], subs: [] };
            if (list && list.items.length && indentOf(ol ? ol[1] : ul[1]) >= 2) {
                const parent = list.items[list.items.length - 1];
                let sub = parent.subs[parent.subs.length - 1];
                if (!sub || sub.kind !== kind) {
                    sub = { kind, start, items: [] };
                    parent.subs.push(sub);
                }
                sub.items.push({ lines: item.lines });
                continue;
            }
            if (!list || list.kind !== kind) {
                list = { kind, start, items: [] };
                blocks.push(list);
            }
            para = null;
            list.items.push(item);
            continue;
        }
        const h = RICH_H.exec(raw);
        if (list && !h && /^[ \t]{2,}/.test(raw) && list.items.length) {
            // An indented line continues the item above it.
            const last = list.items[list.items.length - 1];
            const sub = last.subs[last.subs.length - 1];
            const into = sub ? sub.items[sub.items.length - 1] : last;
            into.lines.push(richInline(raw.trim()));
            continue;
        }
        list = null;
        if (h) {
            blocks.push({ kind: "p", lines: [richInline(h[1], { b: true })] });
            para = null;
            continue;
        }
        if (!para) {
            para = { kind: "p", lines: [] };
            blocks.push(para);
        }
        para.lines.push(richInline(raw.trim()));
    }
    if (RICH_CACHE.size >= RICH_CACHE_MAX) {
        RICH_CACHE.delete(RICH_CACHE.keys().next().value);
    }
    RICH_CACHE.set(src, blocks);
    return blocks;
}

/**
 * AiInsightChat — Floating pill → Centered modal chat for PayAI.
 * Renders as a persistent bottom-right pill that expands into a
 * centered modal with blurred backdrop (inspired by ChatGPT/Intercom).
 */
export class AiInsightChat extends Component {
    static template = "pb_payroll_ai_insights.AiInsightChat";
    static components = { ChartRenderer };
    // LEARN v3. True only for the copy drawn inside the helper drawer.
    static embedded = false;

    setup() {
        // LEARN v3 — ONE HELPER. When pb_learn's helper is installed it is the
        // only floating control, and this chat is its "Ask" tab. The copy
        // mounted in main_components then draws nothing and fetches nothing.
        // Read at setup: every module's assets load before the web client
        // mounts, so the registry is complete by now.
        this.hosted = !this.constructor.embedded
            && registry.category("pb_helper_host").contains("orb");
        this.notification = useService("notification");
        this.actionService = useService("action");
        this.chatBodyRef = useRef("chatBody");
        this.inputRef = useRef("chatInput");
        // ONECHAT OC3 review — words just landed and the box is back on the
        // page after the redraw: focus it (see `_land`, ledger OC56).
        this._wantBoxFocus = false;
        useEffect((ready) => {
            if (ready) {
                this._focusBox();
            }
        }, () => [Boolean(this._wantBoxFocus && this.inputRef.el)]);

        this.state = useState({
            isOpen: false,
            isLoading: false,
            messages: [],
            inputText: "",
            sessionId: null,
            showSuggestions: true,
            aiIconUrl: false,
            isRecording: false,
            recordingDuration: 0,
            // LEARNOS Phase 6 — voice.
            //
            // `voice.available` decides whether a microphone is DRAWN at all.
            // Not disabled-with-a-tooltip: on a database with no speech
            // provider, or a tenant that never switched voice on, or a user
            // who said no, the honest interface has no microphone in it. The
            // server answers this (`rpc_voice_status`) because both gates
            // live there and the browser's copy is a hint, never the control.
            voice: { available: false, ask: false, consent: "unset", copy: {} },
            voiceBusy: false,       // transcribing
            voiceHint: "",          // "this is what I heard" — shown once
            voiceError: "",
            ttsOn: false,
            // ONECHAT OC3 — tap to talk.
            micStarting: false,     // tapped; the recorder has not started
            level: 0,               // the live level meter, 0..1
            hearAs: null,           // "vi" | "en": offer to hear it again
            speakingId: null,       // the turn being read aloud (its Stop)
            sendPulse: false,       // one pulse on Send when words land
        });
        // ONECHAT OC2 — WHERE THE WORDS IN THE BOX CAME FROM (§6.3). A send
        // is "spoken" only when the text sent is exactly what was heard into
        // an EMPTY box: any edit, or typing before speaking, makes it typed.
        // Provenance, not a sticky flag — the old flag rode along with
        // whatever was sent next, a chip included (ledger OC7).
        this._heard = null;
        this._boxBeforeRecording = "";
        // Escape / Cancel while recording: the recorder's `onstop` drops the
        // audio instead of sending it for transcription.
        this._recCancelled = false;
        // ONECHAT OC3 — Stop tapped before the recorder started (the browser
        // still asking for the microphone): applied the moment it starts.
        this._stopWanted = false;
        this._recType = null;
        this._recStartedAt = 0;
        this._recStoppedAt = 0;
        this._peak = 0;
        this._meterRan = false;
        this._audioCtx = null;
        this._meterTimer = null;
        this._pressAt = 0;
        this._pressStarted = false;
        // The last recording, kept in this browser only for "Hear it as …".
        this._keptAudio = null;
        this._landedText = null;
        this._landedBefore = "";

        // Voice recording state
        this._mediaRecorder = null;
        this._audioChunks = [];
        this._recordingTimer = null;
        this._recordingStream = null;
        this._keyHeld = false;
        // M2. Set BEFORE the stream is released on unmount, and re-asked by
        // the recorder's own `onstop`: stopping a MediaRecorder fires that
        // callback asynchronously, so a drawer closed mid-recording would
        // otherwise post the audio it was holding after the component that
        // asked for it no longer exists. The flag is the only thing between
        // "the user closed it" and "a recording left the browser".
        this._discarded = false;

        // ERRORS E4-4. The starter questions a person actually clicks. They
        // were bare literals: untranslated in Vietnamese, and — for the third
        // one — offering a Rize employee a tour of a product they have never
        // heard of. `_t` is both fixes; `String(...)` keeps them primitives so
        // the template and the send path treat them as ordinary text.
        // LEARN REFRESH step 5 — refreshed across the app: running, signing,
        // paying out, a part-month payslip, a leaver, and the tour.
        this.suggestions = [
            _t("How do I run payroll?"),
            _t("Who approves my pay run?"),
            _t("How do I send the bank file and payslips?"),
            _t("Why is a first payslip smaller?"),
            _t("How do I settle someone who is leaving?"),
            _t("Show me around Payobook"),
        ].map(String);

        onMounted(() => {
            if (this.hosted) {
                return;
            }
            this._onMountLoad();
        });
        onWillUnmount(() => {
            // ORDER IS THE CONTROL, not the tidy-up. The discard flag and the
            // emptied buffer come FIRST, before the recorder is touched: a
            // recorder still holding the microphone after the component is
            // gone is a live red dot in the tab strip, and a recorder that
            // fires `onstop` on the way out is an audio POST from a drawer
            // nobody has open.
            this._discarded = true;
            this._audioChunks = [];
            this._keptAudio = null;
            this._releaseMicrophone();
            this._stopSpeaking();
        });
    }

    /** What a mount fetches. The pill: history, icon, voice status. The
     *  helper drawer's copy overrides it (one status call, history only on
     *  the first open of a page). Kept as a promise so a question handed
     *  over is sent AFTER the history lands, not overwritten by it. */
    _onMountLoad() {
        this._historyReady = this._loadHistory();
        this._loadAiIcon();
        this._loadVoiceStatus();
        this._restoreTtsPreference();
    }

    /** A chrome string. The pill has only its own `_t` copy; the helper
     *  drawer's chat reads the helper's, in the pill's language. */
    t(key, fallback) {
        return String(fallback || "");
    }

    // --- UI Actions ---

    togglePanel() {
        this.state.isOpen = !this.state.isOpen;
        if (this.state.isOpen && this.inputRef.el) {
            setTimeout(() => this.inputRef.el?.focus(), 300);
        }
    }

    closePanel() {
        this.state.isOpen = false;
    }

    // --- Message Handling ---

    onInputKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey && !ev.isComposing) {
            ev.preventDefault();
            this.submitComposer();
        }
    }

    onInputChange(ev) {
        this.state.inputText = ev.target.value;
        // Any edit by hand — even retyping the very same words — makes the
        // next send TYPED (§6.3): a spoken go-ahead must be exactly what was
        // heard, untouched.
        this._heard = null;
        // New typing stops anything being read aloud, and the words are no
        // longer the ones heard: "Hear it as …" goes, with the recording.
        this._stopSpeaking();
        if (this._keptAudio && this.state.inputText !== this._landedText) {
            this._dropKeptAudio();
            this.state.voiceHint = "";
        }
    }

    async sendSuggestion(text) {
        this.state.inputText = text;
        this.state.showSuggestions = false;
        await this.sendMessage();
    }

    /** The box's own Send (and Enter). THE ONLY CALLER of `_takeSpoken`:
     *  a chip, a suggestion or a hand-off is never spoken. The helper
     *  drawer's copy overrides this with the router. */
    async submitComposer() {
        const text = this.state.inputText.trim();
        if (!text || this.state.isLoading) {
            return;
        }
        return this.sendMessage({ spoken: this._takeSpoken(text) });
    }

    /** Spoken = the text sent is exactly what was heard into an empty box.
     *  Asked once per send; the answer is used up either way. */
    _takeSpoken(text) {
        const heard = this._heard;
        this._heard = null;
        return heard !== null && String(text || "").trim() === String(heard).trim();
    }

    /** ONECHAT OC2 — ONE ENTRY POINT, with options:
     *    {text?, spoken?, askOnly?, fallbackKey?, pushPerson? = true, extraChips?}
     *  Called with none it is exactly the old send — the box's text, the old
     *  busy guard — so every PayAI card chip and hand-off (`sendSuggestion`)
     *  keeps working unchanged. `text` sends that text without reading or
     *  clearing the box; `pushPerson: false` means the composer already drew
     *  the person's turn; `_fromComposer` means the composer holds the busy
     *  flag itself (route + answer + marker), so it is neither checked nor
     *  cleared here. */
    async sendMessage(opts) {
        const o = isOpts(opts) ? opts : {};
        const own = typeof o.text === "string";
        const text = (own ? o.text : this.state.inputText).trim();
        if (!text) return;
        if (!o._fromComposer && this.state.isLoading) return;
        // The "check what I heard" hint belongs to the text that has now been
        // sent; leaving it over the empty box would read as a warning about
        // the next thing typed.
        this.state.voiceHint = "";
        this.state.voiceError = "";
        // Sent: the kept recording is not needed any more (§6.6).
        this._dropKeptAudio();

        if (o.pushPerson !== false) {
            this._pushMessage({
                role: "user",
                content: text,
                spoken: !!o.spoken,
                chart: null,
                insights: [],
                timestamp: new Date().toISOString(),
            });
        }
        if (!own) {
            this.state.inputText = "";
        }
        this.state.showSuggestions = false;
        this.state.isLoading = true;
        this._scrollToBottom(true);

        try {
            const result = await rpc("/web/dataset/call_kw", {
                model: "payroll.ai.conversation",
                method: "rpc_send_message",
                args: [text, this.state.sessionId, this._currentScreen()],
                // PAYAI P1 — a chip answering a PayAI card rides along here
                // (`pb_payai_actions` fills it; plain questions send nothing).
                // ONECHAT OC2 — and the reader's language (the helper's pill).
                kwargs: { ...this._extraSendKwargs(o), ...this._rpcContext() },
            }, { silent: true });  // suppress Odoo's global spinner — we show typing dots

            this.state.sessionId = result.session_id;

            // ONECHAT OC2 — PayAI could not answer, and the router knew the
            // guide's answer to this: show that instead of an error.
            if (!(result.intent === "error" && o.fallbackKey
                    && await this._fallbackAnswer(o.fallbackKey, o.spoken))) {
                const reply = this._pushMessage({
                    role: "assistant",
                    content: result.response || "",
                    chart: result.chart || null,
                    insights: result.insights || [],
                    followUpQuestions: result.follow_up_questions || [],
                    drillDownModel: result.drilldown_model || "",
                    intent: result.intent || "",
                    action: result.action || null,
                    // PAYAI P1 — the command card (open / show / refuse / ask).
                    card: result.card || null,
                    fresh: !!result.card,
                    // ONECHAT OC2 — "Explain how instead", under the card.
                    extra: o.extraChips && o.extraChips.length ? o.extraChips : null,
                    // Whether the words this answers were spoken: a chip
                    // under it that re-sends them stays spoken.
                    spoken: !!o.spoken,
                    timestamp: new Date().toISOString(),
                });
                // ONECHAT OC3 — a SPOKEN turn is always read back; a typed
                // one only when "Read answers aloud" is on. A plan's own
                // read-back (`card.speak`, pb_payai_actions) replaces this.
                if ((this.state.ttsOn || o.spoken) && !(result.card && result.card.speak)) {
                    // On the device. See the note above `ttsSupported`.
                    this.speak(this._readable(result), reply && reply.id);
                }
            }
        } catch (error) {
            console.error("PayAI error:", error);
            if (!(o.fallbackKey && await this._fallbackAnswer(o.fallbackKey, o.spoken))) {
                this._pushMessage({
                    role: "assistant",
                    content: _t("That did not work. An administrator can check the AI service under PayAI settings."),
                    chart: null,
                    insights: [],
                    timestamp: new Date().toISOString(),
                });
            }
        }

        if (!o._fromComposer) {
            this.state.isLoading = false;
        }
        this._scrollToBottom();
    }

    /** One message into the stream. The helper drawer's copy stamps it. */
    _pushMessage(msg) {
        this.state.messages.push(msg);
        return msg;
    }

    /** The guide's answer in place of a PayAI error. The pill has no guide. */
    async _fallbackAnswer() {
        return false;
    }

    /** What read-aloud says for a reply. Pay figures are NOT read aloud
     *  (owner decision Q2): a data answer says only that they are on screen. */
    _readable(result) {
        const r = result || {};
        if (r.intent === "payroll_data" || r.chart || (r.insights || []).length) {
            return this.t("figuresOnScreen", _t("Here are the figures you asked for — they are on screen."));
        }
        return String(r.response || "").replace(/[*_#`>|]+/g, "");
    }

    /** Extra keyword arguments for `rpc_send_message`. None by default;
     *  `pb_payai_actions` patches this to send a chip's answer, the spoken
     *  flag and `ask_only` (a base database never sees either kwarg). */
    _extraSendKwargs() {
        return {};
    }

    /** The reader's language for the server (`env.lang`). The pill sends
     *  none, as before; the helper drawer's copy sends its pill's. */
    _rpcContext() {
        return {};
    }

    /** True when the next send answers a PayAI card and must not be routed
     *  (pb_payai_actions: a pending `_payaiResolve`). */
    _bypassRouter() {
        return false;
    }

    // Current cockpit, sent with each message so the AI can answer "how do I do
    // THIS?" relative to where the user is standing.
    //
    // LEARN REFRESH step 1: inside a hub the action is the HUB whichever tab
    // is showing, so the hub and tab the hub itself published ride along —
    // plain labels, as the rail shows them ("Pay Run", "Payslips").
    _currentScreen() {
        try {
            const a = this.actionService.currentController && this.actionService.currentController.action;
            if (!a) return null;
            const screen = { tag: a.tag || "", xml_id: a.xml_id || "", model: a.res_model || "", name: a.name || "" };
            if (hubPlace.tag && a.tag === hubPlace.tag) {
                const lens = (hubPlace.lenses || []).find((l) => l.key === hubPlace.lens);
                screen.hub = hubPlace.hubLabel || "";
                screen.tab = lens ? lens.label : "";
            }
            return screen;
        } catch (e) { return null; }
    }

    // --- The "Show me" button: open the lesson the AI recommended ---
    //
    // ONE shape reaches this method. `_sanitize_action` on the server accepts a
    // legacy `start_tour` envelope and CONVERTS it, then always emits
    // `open_lesson` — so a client-side tour branch could never be entered, and
    // one that existed anyway would be a pb_coach dependency kept alive by a
    // path nothing can reach. The legacy acceptance stays where it can actually
    // be exercised: server-side, where the LLM's output arrives.
    runAction(action) {
        if (!action) {
            return;
        }
        // LEARN REFRESH step 2: a walkthrough of the real screens, in Watch
        // mode — the second shape the server's whitelist emits.
        if (action.type === "open_walkthrough" && action.walkthrough) {
            this.closePanel();
            Promise.resolve(
                openHub(this.actionService, {
                    xmlid: "pb_learn.action_learn_hub",
                    lens: "lessons",
                    focus: `scenario:${action.walkthrough}:watch`,
                })
            ).catch(() => {
                this.notification.add(_t("The guided lessons are not installed on this database."),
                                      { type: "warning" });
            });
            return;
        }
        if (action.type !== "open_lesson" || !action.lesson) {
            return;
        }
        this.closePanel();
        // `doAction` is ASYNC — it returns a promise and rejects, it does not
        // throw. A synchronous try/catch around it catches nothing, which is
        // exactly what shipped and what this replaces. The failure is live
        // today: PayAI does not declare pb_learn as a dependency until the
        // deploy-time manifest swap, so on a database without it this click
        // would otherwise surface as an unhandled rejection and no feedback.
        // LEARN REFRESH step 1: the lesson opens inside the Learn hub, on
        // its Lessons tab, so the rail is still there when it finishes.
        // Same deep link, carried as the hub's arrival focus.
        Promise.resolve(
            openHub(this.actionService, {
                xmlid: "pb_learn.action_learn_hub",
                lens: "lessons",
                focus: `lesson:${action.lesson}`,
            })
        ).catch(() => {
            this.notification.add(
                _t("The guided lessons are not installed on this database."),
                { type: "warning" }
            );
        });
    }

    async clearHistory() {
        try {
            await rpc("/web/dataset/call_kw", {
                model: "payroll.ai.conversation",
                method: "rpc_clear_history",
                args: [this.state.sessionId],
                kwargs: {},
            });
            this.state.messages = [];
            this.state.sessionId = null;
            this.state.showSuggestions = true;
            // The drawer confirms in place, in the pill's language; a toast
            // in the account's language on top of it would say it twice.
            if (!this.constructor.embedded) {
                this.notification.add(_t("Chat history cleared"), { type: "info" });
            }
        } catch (error) {
            console.error("Clear history error:", error);
        }
    }

    // --- Pin to Dashboard ---

    async pinToDashboard(chartConfig) {
        if (!chartConfig) return;
        try {
            await rpc("/web/dataset/call_kw", {
                model: "payroll.ai.dashboard",
                method: "rpc_add_widget",
                args: [chartConfig],
                kwargs: {},
            });
            this.notification.add(_t("Chart pinned to dashboard!"), { type: "success" });
        } catch (error) {
            console.error("Pin to dashboard error:", error);
            this.notification.add(_t("Failed to pin chart"), { type: "danger" });
        }
    }

    // ------------------------------------------------------------------
    // VOICE  (LEARNOS Phase 6; tap to talk since ONECHAT OC3)
    //
    // TAP TO TALK, AND THE TRANSCRIPT LANDS IN THE BOX. It does not send
    // (owner decision Q1: the words wait for a tap on Send).
    // The old flow recorded, transcribed and submitted in one gesture, so the
    // first time anybody saw what had been heard was in the transcript of a
    // question already answered — and on a payroll help box that sentence is
    // often a colleague's name and their pay. Now: tap, speak, tap Stop, READ
    // it, then press send like any other question. The server cannot submit
    // either (`rpc_transcribe_voice` returns text and has no send path in it),
    // so this is not a discipline the frontend keeps on its own.
    // ------------------------------------------------------------------

    async _loadVoiceStatus() {
        try {
            const status = await rpc("/web/dataset/call_kw", {
                model: "payroll.ai.conversation",
                method: "rpc_voice_status",
                args: [], kwargs: this._rpcContext(),
            }, { silent: true });
            Object.assign(this.state.voice, status || {});
        } catch {
            // No voice, no microphone drawn. Failing closed is the only
            // acceptable direction for a control that posts audio to a
            // third party.
            this.state.voice.available = false;
            this.state.voice.ask = false;
        }
    }

    get voiceOffered() {
        // ONECHAT OC3 — and a browser that can record here: otherwise the
        // microphone is absent, not broken (§6.2 (c)).
        return !!((this.state.voice.available || this.state.voice.ask) && this.recordingType);
    }

    /** Voice is on for this person, but this browser cannot record: said
     *  once in the hint line, so the missing microphone is explained. */
    get voiceUnsupported() {
        return !!((this.state.voice.available || this.state.voice.ask) && !this.recordingType);
    }

    get voiceCopy() {
        return this.state.voice.copy || {};
    }

    /** NO CONSENT CARD (owner ruling 2026-10-15). The card that asked
     *  "Send recordings for transcription?" before the first recording is
     *  gone: tapping the microphone IS the yes. The server still refuses to
     *  transcribe without a stored "granted" row (`rpc_transcribe_voice`), so
     *  the first tap records that row here, in parallel with the recorder
     *  starting — the recorder must start inside the tap (Safari drops the
     *  microphone permission prompt once an await sits between them), and the
     *  audio only leaves on Stop, by which time `_voiceGranting` has settled
     *  and `_sendForText` waits for it. Also used by the More menu's
     *  "Use my voice" for people who said no on the old card. */
    _grantVoice() {
        if (this._voiceGranting) {
            return this._voiceGranting;
        }
        this.state.voice.consent = "granted";
        this.state.voice.ask = false;
        this.state.voice.available = true;
        this._voiceGranting = rpc("/web/dataset/call_kw", {
            model: "payroll.ai.conversation",
            method: "rpc_set_voice_consent",
            args: [true], kwargs: {},
        }, { silent: true }).catch((error) => {
            console.error("PayAI voice consent error:", error);
        }).finally(() => {
            this._voiceGranting = null;
        });
        return this._voiceGranting;
    }

    // --- tap to talk (ONECHAT OC3) ----------------------------------------
    //
    // TAP TO START, TAP STOP. Press-and-hold still works: a press held longer
    // than HOLD_MS stops on release. Space or Enter on the focused microphone
    // toggles. "Listening" — the red dot, the level meter, the clock — shows
    // only once the recorder has really started (`onstart`): before that the
    // microphone says "Starting…", so nobody speaks into a recorder that is
    // not running yet (a clipped first word turns "Don't go ahead" into "go
    // ahead"). A stop asked for before that moment is remembered and applied
    // the moment it starts (`_stopWanted`), so no silent sixty-second
    // recording is ever sent.
    onMicPointerDown(ev) {
        if (ev && ev.button !== undefined && ev.button !== 0) {
            return;
        }
        if (this.state.isRecording || this.state.micStarting) {
            // The second tap: Stop.
            this._pressStarted = false;
            this._endTalk();
            return;
        }
        this._pressAt = Date.now();
        this._pressStarted = true;
        this._beginTalk();
    }

    onMicPointerUp() {
        // A press HELD past HOLD_MS is press-and-hold: letting go stops it.
        // A quick tap leaves the recorder running until the next tap.
        if (this._pressStarted && Date.now() - (this._pressAt || 0) > HOLD_MS) {
            this._endTalk();
        }
        this._pressStarted = false;
    }

    /** Space / Enter on the focused microphone toggles it. The repeat guard
     *  stops the operating system's key-repeat from toggling it forty times a
     *  second. */
    onMicKeyDown(ev) {
        if (ev.key !== " " && ev.key !== "Enter") {
            return;
        }
        ev.preventDefault();
        if (ev.repeat || this._keyHeld) {
            return;
        }
        this._keyHeld = true;
        if (this.state.isRecording || this.state.micStarting) {
            this._endTalk();
        } else {
            this._beginTalk();
        }
    }

    onMicKeyUp(ev) {
        if (ev.key !== " " && ev.key !== "Enter") {
            return;
        }
        ev.preventDefault();
        this._keyHeld = false;
    }

    /** This browser can record (and in which format), or null. */
    get recordingType() {
        return pickRecordingType();
    }

    _beginTalk() {
        if (this.state.voiceBusy || this.state.isRecording || this.state.micStarting) {
            return;
        }
        if (this.state.voice.ask) {
            // First tap ever: the tap is the agreement (no card).
            this._grantVoice();
        }
        if (!this.state.voice.available) {
            return;
        }
        this._startRecording();
    }

    _endTalk() {
        if (this.state.micStarting) {
            // Not started yet (the browser is still asking for the
            // microphone): remembered, applied the moment it starts.
            this._stopWanted = true;
            return;
        }
        if (this.state.isRecording) {
            this._stopRecording();
        }
    }

    async _startRecording() {
        const type = this.recordingType;
        if (!type) {
            this.state.voiceError = this.t("micUnsupported", "This browser cannot record here.");
            return;
        }
        // Opening the microphone first stops anything being read aloud, and
        // inside this tap (a user gesture) primes the device's speech so a
        // later read-back is allowed (iOS).
        this._stopSpeaking();
        this._primeSpeech();
        // What was in the box when the person started speaking decides
        // whether the words that come back are "spoken" (§6.3).
        this._boxBeforeRecording = this.state.inputText;
        this._recCancelled = false;
        this._stopWanted = false;
        this._recType = type;
        this._peak = 0;
        this._meterRan = false;
        this._recStartedAt = 0;
        this._recStoppedAt = 0;
        this._dropKeptAudio();
        this._mediaRecorder = null;
        // Which start this is: a cancel while the browser is still asking
        // moves it on, so a permission granted late gives its microphone
        // straight back without touching a newer recording.
        const start = (this._startSeq = (this._startSeq || 0) + 1);
        this.state.micStarting = true;
        this.state.voiceError = "";
        this.state.voiceHint = "";
        let stream = null;
        try {
            stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            if (start !== this._startSeq) {
                // Cancelled while the browser was asking (the bar has gone
                // already): nothing records, this microphone is given back.
                stream.getTracks().forEach((t) => t.stop());
                return;
            }
            this._recordingStream = stream;
            if (this._discarded || this._recCancelled) {
                // Closed or cancelled while the browser was asking: nothing
                // records, the microphone is given straight back.
                this._recCancelled = false;
                this._releaseMicrophone();
                return;
            }
            this._audioChunks = [];
            const recorder = new MediaRecorder(stream, { mimeType: type });
            this._mediaRecorder = recorder;

            this._mediaRecorder.ondataavailable = (e) => {
                if (e.data && e.data.size > 0) this._audioChunks.push(e.data);
            };

            this._mediaRecorder.onstart = () => this._onRecorderStart(recorder);
            // The recorder failed on its own (the device went away): nothing
            // is sent, the microphone is given back, and the person is told.
            this._mediaRecorder.onerror = () => {
                this._recCancelled = true;
                this._audioChunks = [];
                this._stopRecording();
                this._releaseMicrophone();
                this.state.voiceError = this.t("micCannot", "This browser could not start the microphone.");
            };

            this._mediaRecorder.onstop = () => {
                const cancelled = this._recCancelled;
                this._recCancelled = false;
                this._recStoppedAt = this._recStoppedAt || Date.now();
                this._releaseMicrophone();
                if (this._discarded) {
                    // The drawer went away while this was recording. Nothing
                    // is sent, and the buffer is already empty.
                    this._audioChunks = [];
                    return;
                }
                if (cancelled) {
                    // Escape or Cancel: this recording is dropped, not sent.
                    this._audioChunks = [];
                    return;
                }
                if (!this._heardEnough()) {
                    // Too short, or silence: never uploaded (ledger OC14).
                    this._audioChunks = [];
                    this.state.voiceHint = this.t("heardNothing",
                        "I didn't hear anything. Tap the microphone and try again.");
                    return;
                }
                this._transcribe();
            };

            this._startMeter(stream);
            this._mediaRecorder.start();
        } catch (err) {
            if (start !== this._startSeq) {
                // A start the person already cancelled: nothing to say.
                return;
            }
            // (b) ANY failure after the browser handed over the microphone
            // gives it straight back — no red dot left in the tab strip.
            this._releaseMicrophone();
            console.warn("PayAI: the microphone did not start", err && err.name);
            this.state.voiceError = err && err.name === "NotAllowedError"
                ? this.t("micDenied", "Microphone access is blocked. Allow it in your browser settings, then try again.")
                : this.t("micCannot", "This browser could not start the microphone.");
        }
    }

    /** The recorder is really running: NOW say "Listening" — unless it was
     *  cancelled (or replaced) before the browser reported the start; then
     *  its own `onstop` gives the microphone back. */
    _onRecorderStart(recorder) {
        if (recorder && (recorder !== this._mediaRecorder || recorder.state !== "recording")) {
            return;
        }
        this._recStartedAt = Date.now();
        this.state.micStarting = false;
        this.state.isRecording = true;
        this.state.recordingDuration = 0;
        this._recordingTimer = setInterval(() => {
            this.state.recordingDuration++;
            // A HARD CEILING. A key that sticks, or a pointer released
            // outside the window, must not leave the microphone open and
            // then post ten minutes of an open-plan office.
            if (this.state.recordingDuration >= MAX_RECORDING_SECONDS) {
                this._endTalk();
            }
        }, 1000);
        if (this._stopWanted) {
            // (a) Stop was tapped while the browser was still asking.
            this._stopWanted = false;
            this._stopRecording();
        }
    }

    /** Long enough, and loud enough at least once, to be worth sending. A
     *  meter that never ran (no Web Audio here) cannot say "silent". */
    _heardEnough() {
        const started = this._recStartedAt || 0;
        const length = started ? (this._recStoppedAt || Date.now()) - started : 0;
        if (length < MIN_RECORDING_MS) {
            return false;
        }
        return !this._meterRan || this._peak >= SILENT_LEVEL;
    }

    /** The live level meter: an AnalyserNode on the same stream, read a
     *  dozen times a second. It also remembers the loudest moment, which is
     *  how a silent recording is told apart (ledger OC14). */
    _startMeter(stream) {
        try {
            const AC = window.AudioContext || window.webkitAudioContext;
            if (!AC) {
                return;
            }
            const ctx = new AC();
            const analyser = ctx.createAnalyser();
            analyser.fftSize = 512;
            ctx.createMediaStreamSource(stream).connect(analyser);
            this._audioCtx = ctx;
            const buf = new Uint8Array(analyser.fftSize);
            const read = () => {
                if (!this._audioCtx) {
                    return;
                }
                analyser.getByteTimeDomainData(buf);
                let sum = 0;
                for (let i = 0; i < buf.length; i++) {
                    const v = (buf[i] - 128) / 128;
                    sum += v * v;
                }
                const rms = Math.sqrt(sum / buf.length);
                this._meterRan = true;
                if (this.state.isRecording) {
                    this._peak = Math.max(this._peak, rms);
                }
                this.state.level = Math.min(1, rms * 4);
                this._meterTimer = setTimeout(read, METER_MS);
            };
            read();
        } catch (e) {
            this._audioCtx = null;
        }
    }

    /** Five bars, heights in percent, from the live level. */
    get levelBars() {
        const level = this.state.level || 0;
        return [0.55, 0.85, 1, 0.8, 0.6].map((w) => Math.round(18 + 82 * Math.min(1, level * w)));
    }

    get recordingClock() {
        const fmt = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
        return `${fmt(this.state.recordingDuration || 0)} / ${fmt(MAX_RECORDING_SECONDS)}`;
    }

    /** Escape while recording, or Cancel: stop, and send nothing. Works while
     *  the browser is still asking for the microphone too. */
    cancelRecording() {
        if (!this.state.isRecording && !this.state.micStarting) {
            return;
        }
        this._recCancelled = true;
        this._audioChunks = [];
        this._dropKeptAudio();
        const live = !!(this._mediaRecorder && this._mediaRecorder.state === "recording");
        this._stopRecording();
        if (this.state.micStarting) {
            // "Starting…" ends NOW — the bar goes and Escape is the drawer's
            // again. With the recorder built, its own `onstop` gives the
            // microphone back; with the browser still asking, this start is
            // moved on, so a late "allow" hands its microphone straight back.
            this._stopWanted = false;
            if (!live) {
                this._startSeq = (this._startSeq || 0) + 1;
                this._recCancelled = false;
                this._releaseMicrophone();
            }
            this.state.micStarting = false;
        }
    }

    _stopRecording() {
        this._recStoppedAt = Date.now();
        if (this._mediaRecorder && this._mediaRecorder.state === 'recording') {
            this._mediaRecorder.stop();
        } else if (this.state.micStarting) {
            this._stopWanted = true;
        }
        this.state.isRecording = false;
        if (this._recordingTimer) {
            clearInterval(this._recordingTimer);
            this._recordingTimer = null;
        }
    }

    _releaseMicrophone() {
        if (this._recordingStream) {
            this._recordingStream.getTracks().forEach((t) => t.stop());
            this._recordingStream = null;
        }
        // (g) the level meter's audio context goes AFTER the tracks.
        if (this._audioCtx) {
            const ctx = this._audioCtx;
            this._audioCtx = null;
            try {
                ctx.close();
            } catch {
                // already closed
            }
        }
        if (this._meterTimer) {
            clearTimeout(this._meterTimer);
            this._meterTimer = null;
        }
        if (this._recordingTimer) {
            clearInterval(this._recordingTimer);
            this._recordingTimer = null;
        }
        this.state.isRecording = false;
        this.state.micStarting = false;
        this.state.level = 0;
    }

    /** Audio out, TEXT INTO THE ASK BAR. Nothing is added to the transcript
     *  and nothing is sent — the learner reads what was heard, edits it if
     *  the microphone misheard a name, and presses send. */
    async _transcribe() {
        if (this._discarded || this._audioChunks.length === 0) {
            return;
        }
        const type = String(this._recType || "audio/webm").split(";")[0];
        const audioBlob = new Blob(this._audioChunks, { type });
        this._audioChunks = [];
        // Kept in this browser's memory only, for "Hear it as …" — dropped on
        // Send, Cancel, a new recording, an edit, close and unmount.
        this._keptAudio = { blob: audioBlob, type };
        await this._sendForText(audioBlob, type, null, true);
    }

    /** "Hear it as Tiếng Việt / English": the SAME recording again, in the
     *  other language. Replaces only what was heard, and only while the box
     *  still holds exactly what landed. */
    async hearAs(lang) {
        const kept = this._keptAudio;
        if (!kept || this.state.voiceBusy || (lang !== "en" && lang !== "vi")) {
            return;
        }
        await this._sendForText(kept.blob, kept.type, lang, false);
    }

    async _sendForText(blob, type, lang, fresh) {
        this.state.voiceBusy = true;
        this.state.voiceError = "";
        this.state.voiceHint = "";
        this.state.hearAs = null;
        try {
            const base64 = await this._toBase64(blob);
            if (this._voiceGranting) {
                // The first-tap agreement is still being saved.
                await this._voiceGranting;
            }
            if (this._discarded) {
                return;
            }
            const result = await rpc("/web/dataset/call_kw", {
                model: "payroll.ai.conversation",
                method: "rpc_transcribe_voice",
                args: [base64],
                kwargs: { lang: lang || null, mime: type, ...this._rpcContext() },
            }, { silent: true });
            if (this._discarded) {
                return;
            }
            if (!result || result.error) {
                this.state.voiceError = (result && result.error)
                    || this.voiceCopy.failed || "";
                return;
            }
            const heard = (result.text || "").trim();
            if (!heard || isPhantomTranscript(heard, this.state.voice.vocab)) {
                // The service invents words on silence and echoes its own
                // hint (ledger OC14): nothing reaches the box.
                this._dropKeptAudio();
                this.state.voiceHint = this.t("heardNothing",
                    "I didn't hear anything. Tap the microphone and try again.");
                return;
            }
            this._land(heard, fresh);
        } catch (error) {
            console.error("PayAI voice error:", error);
            this.state.voiceError = this.voiceCopy.failed || "";
        } finally {
            this.state.voiceBusy = false;
        }
    }

    /** The words land in the box, highlighted by the hint; focus stays in
     *  the box with the cursor at the end (never on Send: a keyboard user who
     *  toggled the microphone with Space would otherwise send half a
     *  sentence with the next key press). */
    _land(heard, fresh) {
        if (fresh) {
            // Appended, not replaced: somebody who typed half a question and
            // then spoke the rest meant both halves — and that mixed text is
            // TYPED. Only words heard into an empty box are spoken (§6.3).
            const before = String(this._boxBeforeRecording || "").trim();
            const existing = this.state.inputText.trim();
            this.state.inputText = existing ? existing + " " + heard : heard;
            this._heard = before || existing ? null : heard;
            this._landedBefore = existing;
        } else {
            // A re-hearing: only the heard part changes.
            const before = this._landedBefore || "";
            this.state.inputText = before ? before + " " + heard : heard;
            this._heard = before ? null : heard;
        }
        this._landedText = this.state.inputText;
        this.state.hearAs = this._keptAudio ? (VI_MARKS.test(heard) ? "en" : "vi") : null;
        this.state.voiceHint = this.voiceCopy.check_hint || "";
        // One pulse on Send: the next step is right there.
        this.state.sendPulse = true;
        setTimeout(() => {
            this.state.sendPulse = false;
        }, 700);
        // The box is NOT on the page yet: "Turning your words into text…"
        // stands in its place until `voiceBusy` clears, and the page redraws
        // a frame later. So the focus is WANTED here and given by the effect
        // below once the box is really there (ledger OC56); the timeout
        // covers a box that never left the page.
        this._wantBoxFocus = true;
        setTimeout(() => this._focusBox(), 0);
    }

    /** Focus the box, cursor at the end — once, and only while wanted. */
    _focusBox() {
        const el = this.inputRef.el;
        if (!this._wantBoxFocus || !el) {
            return;
        }
        this._wantBoxFocus = false;
        el.focus();
        el.selectionStart = el.selectionEnd = el.value.length;
    }

    get hearAsLabel() {
        return this.state.hearAs === "vi"
            ? this.t("hearAsVi", "Hear it as Tiếng Việt")
            : this.t("hearAsEn", "Hear it as English");
    }

    _dropKeptAudio() {
        this._keptAudio = null;
        this._landedText = null;
        this.state.hearAs = null;
    }

    /** CHUNKED. `String.fromCharCode(...bytes)` spreads one argument per byte,
     *  and a thirty-second recording is a million of them — which is a stack
     *  overflow, not a slow path. */
    async _toBase64(blob) {
        const bytes = new Uint8Array(await blob.arrayBuffer());
        let binary = "";
        for (let i = 0; i < bytes.length; i += 0x8000) {
            binary += String.fromCharCode.apply(
                null, bytes.subarray(i, i + 0x8000));
        }
        return btoa(binary);
    }

    // --- speaking the answer --------------------------------------------
    //
    // THE BROWSER'S OWN SYNTHESISER, not the provider's. A reply that has had
    // its placeholders restored is full of real names; posting it to a
    // speech-synthesis endpoint to be read aloud would re-export exactly what
    // the redaction just protected, on the way BACK. `speechSynthesis` runs
    // on the device, so the answer never leaves the browser — which is what
    // makes "the spoken reply is inside the trust boundary" true rather than
    // merely asserted. Documented as a deviation in the Phase 6 report.
    //
    // ONECHAT OC3 — every string handed to the synthesiser goes through
    // `speechText`: markup and markdown out, the brand filter, and NO
    // AMOUNTS (owner decision Q2 — the figures stay on screen). The voice is
    // picked from the text's own language; a device with no Vietnamese voice
    // reads nothing and says so once.

    get ttsSupported() {
        return typeof window !== "undefined" && "speechSynthesis" in window;
    }

    _restoreTtsPreference() {
        try {
            this.state.ttsOn = window.localStorage.getItem(TTS_PREF) === "1";
        } catch {
            this.state.ttsOn = false;
        }
    }

    toggleTts() {
        this.state.ttsOn = !this.state.ttsOn;
        try {
            window.localStorage.setItem(TTS_PREF, this.state.ttsOn ? "1" : "0");
        } catch {
            // A locked-down profile must not break the drawer.
        }
        if (!this.state.ttsOn) {
            this._stopSpeaking();
        }
    }

    /** Inside the first microphone tap: an empty utterance, so the device
     *  allows a later read-back that no tap started (iOS). Once a page. */
    _primeSpeech() {
        if (SPEECH.primed || !this.ttsSupported) {
            return;
        }
        SPEECH.primed = true;
        try {
            window.speechSynthesis.speak(new window.SpeechSynthesisUtterance(""));
        } catch {
            // nothing to prime
        }
    }

    /** `extra.money`: values the plan card marks as money, withheld word
     *  for word (`moneyOfCard`). */
    speak(text, turnId, extra = {}) {
        if (!this.ttsSupported || !text) {
            return;
        }
        if (this.state.isRecording || this.state.micStarting) {
            // Never read aloud into an open microphone.
            return;
        }
        const say = speechText(text, {
            amount: this.t("amountOnScreen", "an amount shown on screen"),
            brand: "Payobook",
            money: (extra && extra.money) || [],
        });
        if (!say) {
            return;
        }
        const lang = VI_MARKS.test(say) ? "vi-VN" : "en-US";
        this._withVoices((voices) => {
            if (this._discarded || this.state.isRecording || this.state.micStarting) {
                return;
            }
            const voice = pickVoice(voices, lang);
            if (!voice && lang === "vi-VN") {
                // No Vietnamese voice here: an English voice reading
                // Vietnamese is noise. Shown, not read — said once.
                if (!SPEECH.noViShown) {
                    SPEECH.noViShown = true;
                    this.state.voiceHint = this.t("noViVoice",
                        "This device has no Vietnamese voice, so answers are shown, not read.");
                }
                return;
            }
            try {
                this._stopSpeaking();
                const utterance = new window.SpeechSynthesisUtterance(say);
                // From the TEXT, not the page: the old read of the page's
                // session info found nothing on this version, so every answer
                // was read in English (ledger OC5).
                utterance.lang = lang;
                if (voice) {
                    utterance.voice = voice;
                }
                const id = turnId || "reading";
                const done = () => {
                    if (this.state.speakingId === id) {
                        this.state.speakingId = null;
                    }
                };
                utterance.onend = done;
                utterance.onerror = done;
                this.state.speakingId = id;
                window.speechSynthesis.speak(utterance);
            } catch (e) {
                console.warn("PayAI speech synthesis failed:", e);
            }
        });
    }

    /** The device's voices — they load late in Chrome (`voiceschanged`). */
    _withVoices(fn) {
        const synth = window.speechSynthesis;
        let list = [];
        try {
            list = synth.getVoices() || [];
        } catch {
            list = [];
        }
        if (list.length || !synth.addEventListener) {
            return fn(list);
        }
        let done = false;
        const once = () => {
            if (done) {
                return;
            }
            done = true;
            try {
                synth.removeEventListener("voiceschanged", once);
            } catch {
                // nothing to remove
            }
            let later = [];
            try {
                later = synth.getVoices() || [];
            } catch {
                later = [];
            }
            fn(later);
        };
        synth.addEventListener("voiceschanged", once);
        setTimeout(once, VOICES_WAIT_MS);
    }

    stopReading() {
        this._stopSpeaking();
    }

    _stopSpeaking() {
        try {
            if (this.ttsSupported) {
                window.speechSynthesis.cancel();
            }
        } catch {
            // Nothing to cancel.
        }
        if (this.state) {
            this.state.speakingId = null;
        }
    }

    formatRecordingTime() {
        const s = this.state.recordingDuration;
        const mins = Math.floor(s / 60);
        const secs = s % 60;
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    // --- Helpers ---

    async _loadAiIcon() {
        try {
            const iconUrl = await rpc("/web/dataset/call_kw", {
                model: "payroll.ai.config",
                method: "rpc_get_ai_icon_url",
                args: [],
                kwargs: {},
            });
            if (iconUrl) {
                this.state.aiIconUrl = iconUrl;
            }
        } catch (error) {
            // Silently fail — will use fallback FA icon
            console.debug("No custom AI icon configured");
        }
    }

    async _loadHistory() {
        try {
            const result = await rpc("/web/dataset/call_kw", {
                model: "payroll.ai.conversation",
                method: "rpc_get_history",
                args: [this.state.sessionId],
                kwargs: {},
            });
            if (result.session_id) {
                this.state.sessionId = result.session_id;
                // ONECHAT OC2 — a row the helper wrote (a marker) is drawn as
                // a marker, and its card is dropped so the PayAI card
                // template never sees it (ledger OC29).
                this.state.messages = (result.messages || []).map((m) => markerOf(m) || m);
                if (this.state.messages.length > 0) {
                    this.state.showSuggestions = false;
                }
            }
        } catch (error) {
            console.error("Load history error:", error);
        }
    }

    _scrollToBottom() {
        setTimeout(() => {
            if (this.chatBodyRef.el) {
                this.chatBodyRef.el.scrollTop = this.chatBodyRef.el.scrollHeight;
            }
        }, 100);
    }

    /** A PayAI answer as the safe block tree (`richBlocks`) the RichText
     *  template draws — bold, lists and line breaks, never HTML. */
    richOf(text) {
        return richBlocks(text);
    }

    formatTimestamp(ts) {
        if (!ts) return "";
        try {
            const d = new Date(ts);
            return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        } catch {
            return "";
        }
    }
}

// Register as a systray item (floating pill)
registry.category("main_components").add("AiInsightChat", {
    Component: AiInsightChat,
});

/* ONECHAT OC2 — the one chat's memory for the page's life. Closing the
   drawer unmounts the chat (that is what discards a recording in progress),
   so the turns are kept HERE and given back on the next open — guide answers
   in full, not as markers. Only a fresh page load reads the history, and
   only then do guide answers come back as markers ("From the guide: …"). */
const PAGE = { sessionId: null, turns: null, status: null };
let TURN_SEQ = 0;
const PRACTICE_BEAT_MS = 600;

/** For tests: forget the page's memory, as a reload would. */
export function _resetPageMemory() {
    PAGE.sessionId = null;
    PAGE.turns = null;
    PAGE.status = null;
}

function rawOf(x) {
    try {
        return (typeof toRaw === "function" && toRaw(x)) || x;
    } catch {
        return x;
    }
}

/**
 * ONECHAT OC2 — THE ONE CHAT, drawn inside the helper drawer.
 *
 * One stream, one composer. Every sentence the person types (or speaks, then
 * sends) goes to the server's router first (`learn.helper.route`), which says
 * where it belongs; this component draws the answer that comes back in the
 * same card frame, whoever wrote it:
 *
 *   payai     → PayAI's own send, unchanged (`sendMessage`, the same RPC,
 *               the same kwargs, plus `ask_only` for a question);
 *   guide / explain / practice / choose / note / miss → a helper turn, drawn
 *               by the drawer's `helper.turnHTML`, and ONE content-free
 *               marker in the person's conversation (`rpc_note_turn`), so
 *               the thread survives a reload and a later spoken "go ahead"
 *               knows the plan is no longer the last thing shown (OC-R3).
 *
 * NEVER THE ROUTER: anything answering a PayAI card (a chip, a pencil, a
 * typed word, a hand-off with a resolve). Those go straight to
 * `sendMessage` / `sendSuggestion`, as they always have (OC-R4).
 *
 * Props: `helper` (from the drawer: guide, context card, practice doors —
 * one object, never re-created), `lang` (the pill: what re-renders past
 * turns in the other language), `screen` / `place` (where the person is),
 * `close`. (The retired Ask tab's `handoff` prop is gone: it sent with
 * `sendSuggestion`, which skips the router and `ask_only`.)
 */
export class AiInsightChatEmbedded extends AiInsightChat {
    static template = "pb_payroll_ai_insights.AiInsightChatEmbedded";
    static embedded = true;
    static props = ["helper?", "lang?", "screen?", "place?", "close?"];

    setup() {
        super.setup();
        this.state.isOpen = true;
        this.state.status = { can_act: false, can_answer: false, voice_go_ahead: false };
        this.state.awayFromBottom = false;
        this._ready = Promise.resolve();
        this.api = this._makeApi();
        onMounted(() => {
            // The drawer's queue (the moment card's Explain, ⌘K) waits for
            // the history: a turn pushed before it lands would be overwritten.
            Promise.resolve(this._historyReady).catch(() => {}).then(() => {
                if (this.props.helper && !this._discarded) {
                    this.props.helper.attach(this.api);
                }
                this._noteScreen(this.props.screen);
            });
            setTimeout(() => this.inputRef.el?.focus(), 80);
        });
        onWillUpdateProps((next) => {
            if ((next.screen || "") !== (this.props.screen || "")) {
                this._noteScreen(next.screen);
            }
        });
        onWillUnmount(() => {
            if (this.props.helper) {
                this.props.helper.detach(this.api);
            }
            PAGE.turns = rawOf(this.state.messages);
            PAGE.sessionId = this.state.sessionId;
        });
    }

    // ------------------------------------------------------------- mount
    /** One status call; the history only on the first open of a page. */
    _onMountLoad() {
        this._restoreTtsPreference();
        const restored = PAGE.turns && PAGE.turns.length ? PAGE.turns : null;
        if (restored) {
            // Given back, not new: nothing fades in again on a re-open.
            for (const m of restored) {
                m.isNew = false;
            }
            this.state.sessionId = PAGE.sessionId;
            this.state.messages = restored;
            this.state.showSuggestions = false;
        }
        if (PAGE.status) {
            this._applyStatus(PAGE.status);
        }
        const status = this._loadHelperStatus();
        this._historyReady = restored ? status : Promise.all([status, this._loadHistory()]);
        this._ready = this._historyReady;
    }

    /** The history, with every row given an id: a marker's "Show again"
     *  and a card's chips find their turn by it. */
    async _loadHistory() {
        await super._loadHistory();
        for (const m of this.state.messages) {
            if (!m.id) {
                m.id = this._turnId();
            }
        }
    }

    async _loadHelperStatus() {
        try {
            const status = await rpc("/web/dataset/call_kw", {
                model: "payroll.ai.conversation",
                method: "rpc_helper_status",
                args: [this.state.sessionId || PAGE.sessionId || null],
                kwargs: this._rpcContext(),
            }, { silent: true });
            PAGE.status = status || {};
            this._applyStatus(PAGE.status);
        } catch {
            // No status: no microphone, the guide still answers, PayAI is
            // tried as before. Failing closed for the microphone is the only
            // acceptable direction for a control that posts audio.
            this.state.voice.available = false;
            this.state.voice.ask = false;
        }
    }

    _applyStatus(status) {
        const st = status || {};
        if (st.session_id && !this.state.sessionId) {
            this.state.sessionId = st.session_id;
        }
        Object.assign(this.state.voice, st.voice || {});
        this.state.status = {
            can_act: !!st.can_act,
            can_answer: !!st.can_answer,
            voice_go_ahead: !!st.voice_go_ahead,
        };
        if (st.icon_url) {
            this.state.aiIconUrl = st.icon_url;
        }
        // Voice is on for this person but this browser cannot record: the
        // missing microphone is explained once a page, never nagged.
        if (this.voiceUnsupported && !SPEECH.unsupportedShown) {
            SPEECH.unsupportedShown = true;
            this.state.voiceHint = this.t("micUnsupported", "This browser cannot record here.");
        }
    }

    // ------------------------------------------------------------- words
    t(key, fallback) {
        const h = this.props.helper;
        const v = h ? h.T(key, this.props.lang) : "";
        return v && v !== key ? v : String(fallback || key);
    }

    pick(pair) {
        const h = this.props.helper;
        if (!pair) {
            return "";
        }
        if (typeof pair === "string") {
            return pair;
        }
        return h ? h.text(pair, this.props.lang) : (pair[this.props.lang] || pair.en || "");
    }

    _rpcContext() {
        const lang = this.props.lang === "vi" ? "vi_VN" : (this.props.lang === "en" ? "en_US" : null);
        if (!lang) {
            return {};
        }
        return { context: { ...((user && user.context) || {}), lang } };
    }

    get placeholder() {
        if (!this.props.helper) {
            return _t("Ask about your payroll…");
        }
        // Only what THIS database can do: pay figures are promised only where
        // the assistant service is set up (`can_answer`); without it the
        // chat answers how things work, as the guide-only stream does.
        const st = this.state.status;
        if (st.can_act) {
            return this.t("askAny");
        }
        return st.can_answer ? this.t("askAnyNoAct") : this.t("askPlaceholder");
    }

    get bannerText() {
        const st = this.state.status;
        if (st.can_act) {
            return this.t("honestAct");
        }
        return st.can_answer ? this.t("honestAsk") : this.t("honestGuide");
    }

    get ttsLabel() {
        return this.t("readAloud", _t("Read answers aloud"));
    }

    // ---------------------------------------------------------- the stream
    _turnId() {
        TURN_SEQ += 1;
        return `c${TURN_SEQ}`;
    }

    _pushMessage(msg) {
        msg.id = msg.id || this._turnId();
        msg.screen = msg.screen === undefined ? (this.props.screen || null) : msg.screen;
        msg.isNew = true;
        this.state.messages.push(msg);
        this._scrollToBottom();
        return this.state.messages[this.state.messages.length - 1];
    }

    /** A turn the helper writes (guide, note, practice, choose, consent,
     *  context, marker). Role "assistant", no card — the PayAI card
     *  template never sees it. */
    _pushHelper(turn) {
        return this._pushMessage(Object.assign({
            role: "assistant", content: "", card: null, chart: null, insights: [],
        }, turn));
    }

    findTurn(id) {
        return this.state.messages.find((m) => m.id === id) || null;
    }

    /** Draw a helper turn through the drawer's renderer (one visual
     *  language with the guide-only stream). Reads `lang` so a flip
     *  re-renders every past turn from the payload it holds. */
    helperTurn(msg) {
        return this.props.helper.turnHTML(msg, this.props.lang, { canAct: this.state.status.can_act });
    }

    contextCard() {
        void this.props.screen;
        void this.props.place;
        return this.props.helper.contextHTML(this.props.lang, { canAct: this.state.status.can_act });
    }

    extraChips(msg) {
        return this.props.helper.chipsHTML(msg.extra, this.props.lang);
    }

    /** "From your pay data" over a PayAI figures answer. */
    sourceLabel(msg) {
        if (msg.role !== "assistant" || msg.card || msg.kind) {
            return "";
        }
        return msg.intent === "payroll_data" || msg.chart ? this.t("fromPayData", _t("From your pay data")) : "";
    }

    /** "Practise this" under a PayAI answer that opens a walkthrough which
     *  can be practised. */
    practiseFor(msg) {
        const a = msg && msg.action;
        if (!this.props.helper || !a || a.type !== "open_walkthrough" || !a.walkthrough) {
            return null;
        }
        return this.props.helper.practiseChip({ try: a.walkthrough });
    }

    /** The screen moved while the conversation has turns: say where we are
     *  now, as the newest item (it collapses once something is sent). */
    _noteScreen(screen) {
        const msgs = this.state.messages;
        if (!msgs.length || !this.props.helper) {
            return;
        }
        const last = msgs[msgs.length - 1];
        if (last.kind === "context" && last.live) {
            last.screen = screen || null;
            last.label = this.props.helper.screenLabelPair();
            return;
        }
        const lastScreen = [...msgs].reverse().find((m) => m.screen !== undefined);
        if (lastScreen && (lastScreen.screen || "") === (screen || "")) {
            return;
        }
        this._pushHelper({ kind: "context", live: true, screen: screen || null,
                           label: this.props.helper.screenLabelPair() });
    }

    /** Sending collapses a live context card to a one-line divider; on an
     *  empty stream the first send leaves a divider naming the screen. */
    _collapseContext() {
        const h = this.props.helper;
        if (!h) {
            return;
        }
        let live = false;
        for (const m of this.state.messages) {
            if (m.kind === "context" && m.live) {
                m.live = false;
                m.label = h.screenLabelPair();
                live = true;
            }
        }
        if (!live && !this.state.messages.length) {
            this._pushHelper({ kind: "context", live: false, label: h.screenLabelPair() });
        }
    }

    // ------------------------------------------------------------ markers
    /** ONE content-free marker for a non-PayAI turn (OC-R3): a kind and a
     *  key, never the question and never any text from this browser. */
    async _marker(kind, key, sourceKind) {
        try {
            const out = await rpc("/web/dataset/call_kw", {
                model: "payroll.ai.conversation",
                method: "rpc_note_turn",
                args: [this.state.sessionId || null, kind, key || null, sourceKind || null,
                       this.props.screen || null],
                kwargs: this._rpcContext(),
            }, { silent: true });
            if (out && out.session_id) {
                this.state.sessionId = out.session_id;
            }
        } catch (e) {
            // A marker that failed loses only the reload copy of this turn.
            console.warn("PayAI: could not record the helper's turn", e);
        }
    }

    /** The marker for a practice or note turn the drawer pushed itself;
     *  the turn is returned as pushed. Not for the question-collection card:
     *  it rides along with the answer it follows, which has its marker. (The
     *  router's "Tap Do it…" notes never come this way — see `_dispatch`.) */
    _markTurn(turn) {
        if (turn && turn.kind === "practice") {
            this._marker("practice", (turn.practice && turn.practice.key) || null);
        } else if (turn && turn.kind === "note" && turn.note && turn.note.key) {
            this._marker("note", turn.note.key);
        }
        return turn;
    }

    /** Which marker a guide answer gets. */
    async _markGuide(answer) {
        if (!answer) {
            return;
        }
        if (!answer.matched) {
            return this._marker("miss", "noAnswer");
        }
        if (answer.source_kind === "composed") {
            return this._marker("composed", null, "composed");
        }
        if (answer.source_kind === "capability" || answer.key === "capability") {
            return this._marker("capability");
        }
        if (answer.source_kind === "screen") {
            return this._marker("explain", answer.key, "screen");
        }
        return this._marker("guide", answer.key, answer.source_kind || null);
    }

    // ------------------------------------------------------------ sending
    /** The box's Send / Enter: the router decides where it goes. */
    async submitComposer() {
        const text = this.state.inputText.trim();
        if (!text || this.state.isLoading) {
            return;
        }
        if (this._bypassRouter() || !this.props.helper) {
            return this.sendMessage({ spoken: this._takeSpoken(text) });
        }
        const spoken = this._takeSpoken(text);
        this.state.inputText = "";
        this._resizeBox();
        await this._routeAndDispatch(text, { spoken });
    }

    /** A sentence from a chip, a suggestion or ⌘K: routed exactly as if
     *  typed, never spoken — unless it answers a PayAI card. */
    async sendText(text, opts = {}) {
        const t = String(text || "").trim();
        if (!t) {
            return;
        }
        if (this._bypassRouter() || !this.props.helper) {
            return this.sendSuggestion(t);
        }
        if (this.state.isLoading) {
            return;
        }
        await this._routeAndDispatch(t, { spoken: false, origin: opts.origin || "chip" });
    }

    async _route(text) {
        const orm = this.env.services && this.env.services.orm;
        const kwargs = {
            screen_key: this.props.screen || null,
            lang: this.props.lang || "en",
            session_id: this.state.sessionId || null,
        };
        if (orm) {
            return orm.call("learn.helper", "route", [text], kwargs);
        }
        return rpc("/web/dataset/call_kw", {
            model: "learn.helper", method: "route", args: [text],
            kwargs: { ...kwargs, ...this._rpcContext() },
        }, { silent: true });
    }

    async _routeAndDispatch(text, { spoken }) {
        // Sent: the kept recording ("Hear it as …") goes, and so does any
        // reading still under way (§6.5, §6.6).
        this._dropKeptAudio();
        this._stopSpeaking();
        this._collapseContext();
        this._pushMessage({ role: "user", content: text, spoken: !!spoken,
                            chart: null, insights: [], timestamp: new Date().toISOString() });
        this.state.isLoading = true;
        this.state.voiceHint = "";
        this.state.voiceError = "";
        this._scrollToBottom(true);
        try {
            let r = null;
            try {
                r = await this._route(text);
            } catch (e) {
                console.warn("PayAI: the router did not answer", e);
            }
            await this._dispatch(text, r, { spoken });
        } finally {
            this.state.isLoading = false;
            this._scrollToBottom();
        }
    }

    /** THE DISPATCH TABLE — the only place a route value is read. */
    async _dispatch(text, r, { spoken }) {
        const h = this.props.helper;
        if (!r || !r.route) {
            this._pushHelper({ kind: "note", note: h.pair("routeFailed") });
            await this._marker("note", "routeFailed");
            return;
        }
        switch (r.route) {
            case "payai":
                await this.sendMessage({
                    text, spoken, askOnly: !!r.ask_only, fallbackKey: r.fallback_key || null,
                    extraChips: r.extra_chips || null, pushPerson: false, _fromComposer: true,
                });
                return;
            case "guide":
                // `spoken` stays on the turn: its chips ("Do it for me")
                // re-send these very words (`sendDirect`).
                this._readHelper(this._pushHelper({ kind: "guide", answer: r.answer, lead: r.lead || null,
                                                    extra: r.extra_chips || null, spoken: !!spoken }), spoken);
                await h.onGuideAnswer(text, r.answer);
                await this._markGuide(r.answer);
                return;
            case "explain":
                await this._pushGuide(await h.explain(), { kind: "explain", spoken });
                return;
            case "practice":
                await this._practiceRoute(r);
                return;
            case "choose":
                this._readHelper(this._pushHelper({ kind: "choose", note: r.note || h.pair("whichMeant"),
                                                    choices: r.choices || [], spoken: !!spoken }), spoken);
                await this._marker("choose", (r.note && r.note.key) || "whichMeant");
                return;
            case "miss":
                if (r.note) {
                    this._readHelper(this._pushHelper({ kind: "note", note: r.note, suggest: r.suggest || [] }), spoken);
                } else {
                    this._readHelper(this._pushHelper({ kind: "guide", answer: r.answer || { matched: false, suggest: r.suggest || [] } }), spoken);
                }
                await h.onGuideAnswer(text, r.answer || { matched: false });
                await this._marker("miss", (r.note && r.note.key) || "noAnswer");
                return;
            case "note":
            default: {
                this._readHelper(this._pushHelper({ kind: "note", note: r.note || h.pair("smalltalk"),
                                                    suggest: r.suggest || [] }), spoken);
                // A note ABOUT the plan card ("Tap Do it…") must not make the
                // plan "not the last thing I showed you" (OC-R3).
                if (r.why !== "tap_card") {
                    await this._marker(r.why === "smalltalk" ? "smalltalk" : "note",
                                       (r.note && r.note.key) || "smalltalk");
                }
            }
        }
    }

    async _practiceRoute(r) {
        const p = r.practice || {};
        if (r.answer) {
            this._pushHelper({ kind: "guide", answer: r.answer });
        }
        this._pushHelper({ kind: "practice", practice: p, note: r.note || null });
        await this._marker("practice", p.key || null);
        // Try starts after a beat; a walkthrough with nothing to practise
        // waits for its own Watch button (the note says why).
        if (p.key && (p.mode === "try" || !r.note)) {
            this._startLater(p.key, p.mode || "try");
        }
    }

    _startLater(key, mode) {
        setTimeout(() => {
            if (this.props.helper) {
                this.props.helper.startPractice(key, mode);
            }
        }, PRACTICE_BEAT_MS);
    }

    /** "Practise this", from a guide answer, a PayAI answer or a chip. */
    async practise(key, mode) {
        const h = this.props.helper;
        if (!h) {
            return;
        }
        this._pushHelper({ kind: "practice", practice: { key, mode: mode || "try",
                                                          name: h.scenarioName(key) || "" } });
        await this._marker("practice", key);
        this._startLater(key, mode || "try");
    }

    async _pushGuide(answer, opts = {}) {
        const h = this.props.helper;
        if (!answer) {
            this._readHelper(this._pushHelper({ kind: "note", note: h.pair("coachNoScreen") }), opts.spoken);
            await this._marker("note", "coachNoScreen");
            return;
        }
        this._readHelper(this._pushHelper({ kind: "guide", answer }), opts.spoken);
        await this._markGuide(answer);
    }

    async _fallbackAnswer(key, spoken) {
        const h = this.props.helper;
        if (!h || !key) {
            return false;
        }
        const answer = await h.answerFor(key);
        if (!answer || !answer.matched) {
            return false;
        }
        this._readHelper(this._pushHelper({ kind: "guide", answer }), spoken);
        await this._markGuide(answer);
        return true;
    }

    /** ONECHAT OC3 — read a helper turn back (§6.5): always after a SPOKEN
     *  sentence, else only with "Read answers aloud" on. A guide answer is
     *  read as plain words (no source line, no worked figures); a note or a
     *  choice reads its line. A practice turn is not read — the practice
     *  opens and the drawer closes. */
    _readHelper(turn, spoken) {
        const h = this.props.helper;
        if (!turn || !h || !(spoken || this.state.ttsOn)) {
            return;
        }
        const lang = this.props.lang;
        let text = "";
        if (turn.kind === "guide") {
            text = h.answerSpeech ? h.answerSpeech(turn.answer, lang) : "";
            if (turn.lead) {
                text = `${this.pick(turn.lead)} ${text}`;
            }
        } else if (turn.kind === "note") {
            text = this.pick(turn.note);
        } else if (turn.kind === "choose") {
            const labels = (turn.choices || []).map((c) => this.pick(c.label)).filter(Boolean);
            text = [this.pick(turn.note), labels.join(". ")].filter(Boolean).join(" ");
        }
        if (text) {
            this.speak(text, turn.id);
        }
    }

    // --------------------------------------------------------------- api
    /** What the drawer may ask of this chat (`helper.attach`). */
    _makeApi() {
        const ready = (fn) => Promise.resolve(this._ready).catch(() => {}).then(fn);
        return {
            pushGuide: (answer, opts) => ready(() => this._pushGuide(answer, opts)),
            pushNote: (note) => ready(() => this._markTurn(this._pushHelper({ kind: "note", note }))),
            // A turn the drawer draws by itself (the practice chips of "Let
            // me practise this", "That control is not on this screen") is a
            // non-PayAI turn like any other: it writes its marker (OC-R3).
            pushTurn: (turn) => this._markTurn(this._pushHelper(Object.assign({}, turn))),
            sendText: (text, opts) => ready(() => this.sendText(text, opts)),
            // False when PayAI is still answering: nothing was sent, and the
            // chip that asked stays usable (the drawer un-picks a choice).
            // `spoken`: the chip re-sends words that were heard (the turn it
            // sits under says so) — kept, so a plan from them still needs a
            // tap (Q6). Never set for anything typed.
            sendDirect: ({ text, askOnly, spoken }) => ready(async () => {
                if (this.state.isLoading) {
                    return false;
                }
                await this.sendMessage({ text, askOnly: !!askOnly, spoken: spoken === true });
                return true;
            }),
            practise: (key, mode) => this.practise(key, mode),
            findTurn: (id) => this.findTurn(id),
            dropTurns: (kind) => {
                this.state.messages = this.state.messages.filter((m) => m.kind !== kind);
            },
            isEmpty: () => !this.state.messages.length,
            focus: () => this.inputRef.el && this.inputRef.el.focus(),
            setDraft: (text) => {
                this.state.inputText = String(text || "");
            },
            clear: () => this.clearHistory(),
            toggleReadAloud: () => this.toggleTts(),
            readAloudOn: () => !!this.state.ttsOn,
            ttsSupported: () => this.ttsSupported,
            voiceDeclined: () => !!(this.state.voice.consent === "declined"
                && this.state.voice.switch_on && this.state.voice.provider_ready),
            // "Use my voice" (More menu): no card any more, it just turns the
            // microphone back on. Name kept so pb_learn's coach still calls it.
            reopenVoiceConsent: () => this._grantVoice(),
            cancelRecording: () => this.cancelRecording(),
            // "Starting…" counts: Escape then cancels before anything records.
            isRecording: () => !!(this.state.isRecording || this.state.micStarting),
        };
    }

    async clearHistory() {
        if (!this.state.sessionId) {
            this.state.messages = [];
            PAGE.turns = null;
            return;
        }
        await super.clearHistory();
        PAGE.turns = null;
        PAGE.sessionId = null;
    }

    // ------------------------------------------------------------- input
    onInputChange(ev) {
        super.onInputChange(ev);
        this._resizeBox(ev.target);
    }

    /** One to five lines, then it scrolls. */
    _resizeBox(el) {
        const box = el || this.inputRef.el;
        if (!box || !box.style) {
            return;
        }
        box.style.height = "auto";
        box.style.height = `${Math.min(box.scrollHeight || 0, 120)}px`;
    }

    // ------------------------------------------------------------ scroll
    /** Sticks to the bottom while the person is there; when they have
     *  scrolled up to read, a "Jump to latest" pill appears instead. */
    _scrollToBottom(force) {
        setTimeout(() => {
            const el = this.chatBodyRef.el;
            if (!el) {
                return;
            }
            if (force || !this.state.awayFromBottom) {
                el.scrollTop = el.scrollHeight;
                this.state.awayFromBottom = false;
            }
        }, 60);
    }

    onBodyScroll(ev) {
        const el = ev.target;
        this.state.awayFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight > 80;
    }

    jumpToLatest() {
        this.state.awayFromBottom = false;
        this._scrollToBottom(true);
    }

    /** "Show me" opens a lesson, which closes the whole drawer. */
    closePanel() {
        if (this.props.close) {
            this.props.close();
        }
    }
}

const ONE_CHAT = {
    Component: AiInsightChatEmbedded,
    // The drawer draws the chat only for people who hold one of these; for
    // anyone else every question would fail on the conversation's access
    // rule, and the drawer draws its guide-only stream instead.
    groups: ["pb_payroll_ai_insights.group_payai_user"],
};
registry.category("pb_helper_chat").add("main", ONE_CHAT);
// The old seam's name, for one release: a drawer bundle that still reads
// `pb_helper_tabs/ask` finds the same chat. Remove with the drawer's shim.
registry.category("pb_helper_tabs").add("ask", ONE_CHAT);
