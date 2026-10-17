/**
 * GAPS (4b) — PayAI's door buttons in the reader's language, the browser half.
 *
 * A ⌘K row's label is a _t() string made before the translations loaded: it
 * READS in the screens' language and keeps the words as written in the code
 * underneath. The chat now sends both (label + label_src), so the server can
 * draw "Mở Trang chủ › Phê duyệt" for a Vietnamese reader on English screens
 * (the server half is pb_payai_actions/tests/offline/test_gaps_doors.py).
 *
 * Run: node pb_payai_actions/tests/js/gaps_doors.test.mjs   (exit 1 on failure)
 */
import { check, load, summary } from "./harness.mjs";

const pb = globalThis.__pb;
const rpcLog = [];
pb.rpc = async (route, params) => {
    rpcLog.push(params);
    return { session_id: 7 };
};

const CHAT = "@pb_payroll_ai_insights/components/ai_insight_chat/ai_insight_chat";
const chatMod = await load(CHAT);
const patchMod = await load("@pb_payai_actions/js/chat_patch", [CHAT, "@pb_hub/js/hub_nav"]);
const { wordsOf } = patchMod;
const chatPatch = pb.patches.find((p) => p.target === chatMod.AiInsightChat.prototype
    && typeof p.obj._payaiRegisterDoors === "function");

/** The web client's lazy translated string: reads translated, holds the source. */
class Lazy extends String {
    constructor(source, translated) {
        super(source);
        this.translated = translated;
    }
    toString() { return this.translated; }
    valueOf() { return this.translated; }
}

// ------------------------------------------------------------- wordsOf
const approvals = new Lazy("Approvals", "Phê duyệt");
check(String(approvals) === "Phê duyệt", "a lazy label reads in the screens' language");
check(wordsOf(approvals) === "Approvals", "wordsOf gives the words as written in the code");
check(wordsOf("Phê duyệt") === "Phê duyệt", "a plain string is sent as it reads");
check(wordsOf(undefined) === "" && wordsOf(null) === "", "nothing is an empty string");
check(wordsOf(new String("Runs")) === "Runs", "a String object is its own words");

// --------------------------------------------------- the registered rows
const chat = Object.create(chatPatch.obj);
chat.state = { sessionId: 3 };
chat._historyReady = Promise.resolve();
chat.env = {
    services: {
        pb_hub_palette: {
            entries: async () => [
                { id: "homehub_approvals", label: approvals, sublabel: new Lazy("Home", "Trang chủ"),
                  groups: [] },
                { id: "learn.station.filing", label: "Báo cáo nộp cơ quan nhà nước",
                  sublabel: "Bài học · 5 phút", groups: [] },
                { id: "payai_ask", label: "Ask PayAI", anyQuery: true },
            ],
        },
    },
};
await chat._payaiRegisterDoors();
const sent = rpcLog.find((p) => p && p.method === "rpc_register_doors");
check(!!sent, "the rows were registered");
const rows = (sent && sent.args[1]) || [];
const row = rows.find((r) => r.id === "homehub_approvals") || {};
check(row.label === "Phê duyệt" && row.sublabel === "Trang chủ",
      "the label still reads as the screens show it (matching reads it)", JSON.stringify(row));
check(row.label_src === "Approvals" && row.sublabel_src === "Home",
      "… and carries the words under the translation", JSON.stringify(row));
const learn = rows.find((r) => r.id === "learn.station.filing") || {};
check(learn.label_src === learn.label, "a row built from plain text sends its own words",
      JSON.stringify(learn));
check(!rows.find((r) => r.id === "payai_ask"), "the any-query row is still never a door");

summary();
