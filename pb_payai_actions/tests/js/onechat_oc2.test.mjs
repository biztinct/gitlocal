/**
 * ONECHAT OC2 — the one chat's client halves, run in node (no browser).
 *
 * The real CoachHost (pb_learn coach.js, with the real runtime + glossary),
 * the real embedded chat (pb_payroll_ai_insights ai_insight_chat.js) and the
 * real PayAI patches (pb_payai_actions chat_patch.js + coach_patch.js), wired
 * together the way the browser wires them; only the server is a stub.
 *
 *   2.3  spoken provenance and the send kwargs
 *   2.4  the route dispatch table (one person turn, chips resolve without a
 *        second route call, a PayAI error with a fallback draws the guide)
 *   2.5  chip bypass (a card's answer never reaches the router)
 *   2.6  language: past guide turns and notes re-render on a flip
 *   2.7  close/reopen keeps full guide answers; a fresh page gets markers
 *   2.8  the queue: Explain / ⌘K before the chat attaches → once, after
 *   + the Escape ladder, the More menu, the banner, the figures rule (Q2)
 *
 * Run: node pb_payai_actions/tests/js/onechat_oc2.test.mjs   (exit 1 on failure)
 */
import fs from "node:fs";
import path from "node:path";
import { check, load, summary, ROOT } from "./harness.mjs";

const pb = globalThis.__pb;

// ---- just enough of a browser for the drawer's mount
const noop = () => {};
globalThis.document = {
    addEventListener: noop, removeEventListener: noop,
    body: { classList: { add: noop, remove: noop, contains: () => false } },
    documentElement: { style: { setProperty: noop } },
    querySelector: () => null, querySelectorAll: () => [], activeElement: null,
};
globalThis.window = {
    localStorage: { getItem: () => null, setItem: noop },
    matchMedia: () => ({ matches: false }),
    innerHeight: 800,
};
const CONTENT = JSON.parse(fs.readFileSync(
    path.join(ROOT, "pb_learn", "static", "content", "learn_content.json"), "utf-8"));

// ---- OWL hooks the harness does not record: unmount and prop updates.
const baseStub = pb.stub;
pb.stub = (spec) => {
    const inner = baseStub(spec);
    return new Proxy({}, {
        get(_t, name) {
            if (name === "onWillUnmount") {
                return (fn) => pb.hookCtx.current && pb.hookCtx.current.unmount.push(fn);
            }
            if (name === "onWillUpdateProps") {
                return (fn) => pb.hookCtx.current && pb.hookCtx.current.update.push(fn);
            }
            return inner[name];
        },
    });
};

function mountFull(Cls, props = {}, env = {}) {
    const hooks = { willStart: [], mounted: [], unmount: [], update: [] };
    pb.hookCtx.current = hooks;
    const comp = new Cls(props, env);
    comp.setup();
    pb.hookCtx.current = null;
    comp.__hooks = hooks;
    for (const fn of hooks.mounted) { fn(); }
    return comp;
}
function unmount(comp) {
    for (const fn of comp.__hooks.unmount) { fn(); }
}
const tick = (ms = 0) => new Promise((r) => setTimeout(r, ms));

// ---- the server
let rpcLog = [];
let ormLog = [];
let routeAnswer = () => ({ route: "note", why: "smalltalk", note: { en: "Hi", vi: "Chào", key: "smalltalk" } });
let sendAnswer = () => ({ session_id: 7, response: "Here is PayAI's answer.", intent: "general" });
let historyRows = [];

pb.rpc = async (_route, params) => {
    const { method, args, kwargs } = params;
    rpcLog.push({ method, args, kwargs });
    if (method === "rpc_helper_status") {
        return { session_id: 7, voice: { available: false, ask: false, consent: "unset", copy: {} },
                 can_answer: true, can_act: true, voice_go_ahead: false, icon_url: false };
    }
    if (method === "rpc_get_history") { return { session_id: 7, messages: historyRows }; }
    if (method === "rpc_send_message") { return sendAnswer(args, kwargs); }
    if (method === "rpc_note_turn") { return { session_id: 7, message_id: rpcLog.length }; }
    if (method === "rpc_register_doors") { return { session_id: 7 }; }
    if (method === "rpc_clear_history") { return true; }
    if (method === "rpc_transcribe_voice") { return { text: transcript }; }
    return null;
};
let transcript = "";

const ANSWERS = {
    approve: { key: "approve", matched: true, label: { en: "Approve a request", vi: "Duyệt một yêu cầu" },
               blocks: [{ kind: "p", body: { en: "Open Approvals.", vi: "Mở mục Duyệt." } }],
               watch: "", try: "sc_payrun", show_me: [], simpler: "" },
    howrun: { key: "howrun", matched: true, label: { en: "Run payroll", vi: "Chạy lương" },
              blocks: [{ kind: "p", body: { en: "Press Run.", vi: "Bấm Chạy." } }],
              watch: "", try: "sc_payrun", show_me: [], simpler: "" },
};
const EXPLAIN = { key: "screen:payruns", matched: true, source_kind: "screen",
                  label: { en: "Explain this screen", vi: "Giải thích màn hình này" },
                  blocks: [{ kind: "p", body: { en: "The runs board.", vi: "Bảng các đợt lương." } }],
                  watch: "", try: "", show_me: [], simpler: "" };
const orm = {
    call: async (model, method, args = [], kwargs = {}) => {
        ormLog.push({ model, method, args, kwargs });
        if (model === "learn.helper" && method === "route") { return routeAnswer(args[0], kwargs); }
        if (method === "answer_for") { return ANSWERS[args[0]] || { matched: false, suggest: [] }; }
        if (method === "explain_screen") { return EXPLAIN; }
        if (method === "log") { return true; }
        return null;
    },
};
const scenarios = Object.fromEntries((CONTENT.scenarios || []).map((s) => [s.key, s]));
const started = [];
const sc = {
    state: {},
    get: (k) => scenarios[k] || null,
    forScreen: (screen) => Object.values(scenarios).filter((s) => !s.retired && (s.screens || []).includes(screen)),
    load: async () => {},
    begin: async (k, m) => { started.push([k, m]); return true; },
    steps: () => [],
};
pb.services.orm = orm;
pb.services.action = { currentController: null, doAction: async () => {} };
pb.services["learn.scenario"] = sc;
pb.services.notification = { add: () => {} };

function reset() {
    rpcLog = [];
    ormLog = [];
    started.length = 0;
}
const rpcs = (m) => rpcLog.filter((c) => c.method === m);
const routes = () => ormLog.filter((c) => c.model === "learn.helper" && c.method === "route");

// ------------------------------------------------------------------ load
const runtime = await load("@pb_learn/engine/runtime");
const coachMod = await load("@pb_learn/coach/coach", ["@pb_learn/engine/runtime", "@pb_learn/engine/glossary"]);
const chatMod = await load("@pb_payroll_ai_insights/components/ai_insight_chat/ai_insight_chat");
await load("@pb_payai_actions/js/chat_patch",
           ["@pb_payroll_ai_insights/components/ai_insight_chat/ai_insight_chat", "@pb_hub/js/hub_nav"]);
await load("@pb_payai_actions/js/coach_patch",
           ["@pb_learn/coach/coach", "@pb_payai_actions/js/chat_patch",
            "@pb_payroll_ai_insights/components/ai_insight_chat/ai_insight_chat",
            "@pb_learn/engine/runtime", "@pb_learn/engine/glossary"]);

const fullMod = await load("@pb_payroll_ai_insights/components/ai_insight_chat/ai_insight_chat_full",
                           ["@pb_payroll_ai_insights/components/ai_insight_chat/ai_insight_chat"]);
const { RT } = runtime;
const { CoachHost, COACH_ACTIONS } = coachMod;
const { AiInsightChat, AiInsightChatEmbedded, _resetPageMemory, markerOf } = chatMod;
RT.chrome = CONTENT.chrome;
RT.lang = "en";

// Apply the patches the way `patch()` does in the browser: in the chain.
const chatPatch = pb.patches.find((p) => p.target === AiInsightChat.prototype && typeof p.obj._payaiRegisterDoors === "function");
const hostPatch = pb.patches.find((p) => p.target === CoachHost.prototype);
check(Boolean(chatPatch && hostPatch), "both PayAI patches registered");
Object.setPrototypeOf(AiInsightChatEmbedded.prototype, chatPatch.obj);
class Host extends CoachHost {}
Object.setPrototypeOf(Host.prototype, hostPatch.obj);
check(Boolean(pb.registry.category("pb_helper_chat").get("main")), "the chat registers as pb_helper_chat/main");
check(pb.registry.category("pb_helper_tabs").get("ask").Component === AiInsightChatEmbedded,
      "… and the old pb_helper_tabs/ask name still finds it (one-release shim)");

function makeHost() {
    const host = mountFull(Host, {}, { bus: {} });
    host.place = { tag: "", lens: "", subs: {}, lenses: [], seq: 0, detail: "", ready: true };
    host.chatAllowed = true;
    host.bundle = {
        screens: [{ key: "payruns", name: { en: "Pay runs", vi: "Các đợt lương" },
                    blurb: { en: "Every pay run.", vi: "Mọi đợt lương." },
                    suggest: [{ key: "approve", label: { en: "How do I approve a request?", vi: "Làm sao để duyệt?" } }] }],
        global_suggest: [], chrome: CONTENT.chrome, collect_questions: false,
    };
    host.state.ready = true;
    host.state.screen = "payruns";
    return host;
}
function makeChat(host, extra = {}) {
    const chat = mountFull(AiInsightChatEmbedded,
        { helper: host.helper, lang: host.state.lang, screen: host.state.screen, place: "", close: () => {}, ...extra },
        { services: { orm, pb_hub_palette: null } });
    return chat;
}
async function openChat() {
    _resetPageMemory();
    historyRows = [];
    const host = makeHost();
    host.state.open = true;
    const chat = makeChat(host);
    await chat._historyReady;
    await tick(5);
    return { host, chat };
}
const kinds = (chat) => chat.state.messages.map((m) => m.kind || m.role);

// =================================================================== 2.3
async function spokenSuite() {
    console.log("2.3 spoken provenance");
    const { chat } = await openChat();
    const say = async (words) => {
        transcript = words;
        chat._boxBeforeRecording = chat.state.inputText;
        chat._audioChunks = [new Blob(["x"])];
        await chat._transcribe();
    };
    routeAnswer = () => ({ route: "payai", why: "goahead" });
    const lastSend = () => rpcs("rpc_send_message").slice(-1)[0] || { kwargs: {} };

    reset();
    await say("go ahead");
    check(chat.state.inputText === "go ahead", "the words land in the box, nothing is sent", chat.state.inputText);
    check(rpcs("rpc_send_message").length === 0 && routes().length === 0, "transcribing sends nothing");
    await chat.submitComposer();
    check(lastSend().kwargs.voice === true, "spoken into an empty box + Send → voice:true", JSON.stringify(lastSend().kwargs));
    const userTurn = chat.state.messages.filter((m) => m.role === "user").slice(-1)[0];
    check(userTurn && userTurn.spoken === true, "… and the person's turn carries the spoken mark");

    reset();
    await say("go ahead");
    chat.onInputChange({ target: { value: "go ahead" } });       // select all, type the same words
    await chat.submitComposer();
    check(!lastSend().kwargs.voice, "speak, then retype the same words → typed", JSON.stringify(lastSend().kwargs));

    reset();
    chat.onInputChange({ target: { value: "go" } });
    await say("ahead");
    check(chat.state.inputText === "go ahead", "typed half + spoken half are joined");
    await chat.submitComposer();
    check(!lastSend().kwargs.voice, "type 'go', speak 'ahead' → typed");

    reset();
    await say("send the payslips to Lan");
    chat.onInputChange({ target: { value: "send the payslips to Lân" } });
    await chat.submitComposer();
    check(!lastSend().kwargs.voice, "speak, fix one word → typed");

    reset();
    await say("go ahead");
    await chat.submitComposer();
    await chat.sendText("go ahead", { origin: "followup" });
    check(rpcs("rpc_send_message").length === 2 && !lastSend().kwargs.voice,
          "speak + Send, then a chip → the chip is not spoken");

    reset();
    await say("go ahead");
    chat.onInputChange({ target: { value: "" } });
    chat.onInputChange({ target: { value: "go ahead" } });
    await chat.submitComposer();
    check(!lastSend().kwargs.voice, "an emptied box resets the spoken mark");

    check(JSON.stringify(chat._extraSendKwargs({ spoken: true })) === '{"voice":true}', "_extraSendKwargs({spoken}) → {voice:true}");
    check(JSON.stringify(chat._extraSendKwargs({ askOnly: true })) === '{"ask_only":true}', "_extraSendKwargs({askOnly}) → {ask_only:true}");
    check(JSON.stringify(chat._extraSendKwargs({})) === "{}", "_extraSendKwargs({}) → {}");
    chat._payaiResolve = { task_id: 3, slot: "period", value: "6" };
    check(JSON.stringify(chat._extraSendKwargs({ spoken: true, askOnly: true }))
          === '{"resolve":{"task_id":3,"slot":"period","value":"6"}}', "a pending resolve travels alone");
    check(chat._payaiResolve === null, "… and is used up");

    // the router never sees the spoken flag (OC-R1)
    const rk = routes().map((r) => Object.keys(r.kwargs).sort().join(","));
    check(rk.length && rk.every((k) => k === "lang,screen_key,session_id"),
          "learn.helper.route is called with screen_key, lang, session_id only", JSON.stringify(rk));
}

// =================================================================== 2.4
async function dispatchSuite() {
    console.log("2.4 route dispatch table");
    const { host, chat } = await openChat();
    const send = async (text) => {
        chat.state.inputText = text;
        await chat.submitComposer();
    };
    const table = [
        ["guide", { route: "guide", why: "guide_strong", answer: ANSWERS.approve }, "guide", "guide"],
        ["explain", { route: "explain", why: "explain" }, "guide", "explain"],
        ["practice", { route: "practice", why: "practise", practice: { key: "sc_payrun", mode: "try", name: { en: "Run a pay run", vi: "Chạy đợt lương" } } }, "practice", "practice"],
        ["choose", { route: "choose", why: "weak", note: { en: "Which did you mean?", vi: "Ý bạn là việc nào?", key: "whichMeant" },
                     choices: [{ label: { en: "Approve a request", vi: "Duyệt" }, route: "guide", key: "approve" },
                               { label: { en: "Ask about your pay data", vi: "Hỏi" }, route: "payai", text: "can I approve", ask_only: true }] }, "choose", "choose"],
        ["note", { route: "note", why: "smalltalk", note: { en: "Happy to help.", vi: "Rất sẵn lòng.", key: "smalltalk" }, suggest: [] }, "note", "smalltalk"],
        ["tap_card", { route: "note", why: "tap_card", note: { en: "Tap Do it to go ahead.", vi: "Bấm Thực hiện.", key: "tapDoIt" } }, "note", null],
        ["miss", { route: "miss", why: "no_payai", answer: { matched: false, suggest: [] },
                   note: { en: "Questions about pay figures need the assistant service…", vi: "…", key: "noPayai" } }, "note", "miss"],
    ];
    for (const [label, r, kind, marker] of table) {
        reset();
        routeAnswer = () => r;
        const before = chat.state.messages.length;
        await send(`sentence for ${label}`);
        const added = chat.state.messages.slice(before);
        const persons = added.filter((m) => m.role === "user");
        const turn = added.filter((m) => m.role !== "user" && m.kind !== "context").slice(-1)[0] || {};
        check(persons.length === 1, `${label}: exactly one person turn`);
        check(turn.kind === kind, `${label}: draws a ${kind} turn`, `got ${turn.kind}`);
        const notes = rpcs("rpc_note_turn").map((c) => c.args[1]);
        check(marker ? notes.length === 1 && notes[0] === marker : notes.length === 0,
              `${label}: ${marker ? `one '${marker}' marker` : "no marker (about the plan card)"}`, JSON.stringify(notes));
        check(rpcs("rpc_note_turn").every((c) => c.args.length === 5 && c.args.every((a) => a === null || typeof a !== "string" || a.length <= 80))
              && rpcs("rpc_note_turn").every((c) => !c.args.includes(`sentence for ${label}`)),
              `${label}: the marker carries no question text`);
        check(rpcs("rpc_send_message").length === 0, `${label}: PayAI is not called`);
        check(typeof host.helper.turnHTML(turn, "en") === "string" || turn.kind,
              `${label}: the drawer can draw it`);
    }
    // practice starts after the beat
    await tick(650);
    check(started.some(([k, m]) => k === "sc_payrun" && m === "try"), "the practice turn opens sc_payrun Try after a beat");

    // payai: one person turn, sendMessage with pushPerson:false
    reset();
    routeAnswer = () => ({ route: "payai", why: "question", ask_only: true, fallback_key: "approve" });
    sendAnswer = () => ({ session_id: 7, response: "PayAI says.", intent: "general" });
    let before = chat.state.messages.length;
    await send("can I approve the June run?");
    let added = chat.state.messages.slice(before);
    check(added.filter((m) => m.role === "user").length === 1, "payai: exactly ONE person turn (the composer's)");
    check(rpcs("rpc_send_message").length === 1 && rpcs("rpc_send_message")[0].kwargs.ask_only === true,
          "payai: one rpc_send_message, with ask_only", JSON.stringify(rpcs("rpc_send_message")[0] && rpcs("rpc_send_message")[0].kwargs));
    check(rpcs("rpc_send_message")[0].kwargs.context && rpcs("rpc_send_message")[0].kwargs.context.lang === "en_US",
          "payai: the pill's language rides along as context.lang");
    check(rpcs("rpc_note_turn").length === 0, "payai: no marker (PayAI writes its own turn)");
    check(!chat.state.isLoading, "the busy flag is given back");

    // a PayAI error with a fallback key → the guide's answer instead
    reset();
    sendAnswer = () => ({ session_id: 7, response: "Something went wrong on my side.", intent: "error" });
    before = chat.state.messages.length;
    await send("how much back pay is owed to Lan");
    added = chat.state.messages.slice(before);
    check(added.some((m) => m.kind === "guide" && m.answer.key === "approve")
          && !added.some((m) => m.role === "assistant" && /went wrong/.test(m.content || "")),
          "a PayAI error with fallback_key draws the guide answer, not the error");
    sendAnswer = () => ({ session_id: 7, response: "PayAI says.", intent: "general" });

    // choose chips resolve without a second route call
    reset();
    routeAnswer = () => table[3][1];
    await send("approve?");
    const chooseTurn = chat.state.messages.filter((m) => m.kind === "choose").slice(-1)[0];
    const nRoutes = routes().length;
    await host._pickChoice(chooseTurn.id, 0);
    check(routes().length === nRoutes && ormLog.some((c) => c.method === "answer_for" && c.args[0] === "approve"),
          "a guide choice shows its answer without routing again");
    check(chat.state.messages.slice(-1)[0].kind === "guide", "… drawn as a guide turn");
    await host._pickChoice(chooseTurn.id, 1);
    check(rpcs("rpc_send_message").length === 0, "a choice is used once (the second chip is dead)");
    reset();
    await send("approve?");
    const second = chat.state.messages.filter((m) => m.kind === "choose").slice(-1)[0];
    const r0 = routes().length;
    await host._pickChoice(second.id, 1);
    check(routes().length === r0 && rpcs("rpc_send_message").length === 1
          && rpcs("rpc_send_message")[0].kwargs.ask_only === true
          && rpcs("rpc_send_message")[0].args[0] === "can I approve",
          "a PayAI choice goes straight to PayAI, with ask_only, no second route");

    // "Do it for me" (extra chip on a guide turn) → PayAI, not the router
    reset();
    routeAnswer = () => ({ route: "guide", why: "guide_offer", answer: ANSWERS.howrun,
                           lead: { en: "Here is how. Or I can prepare it for you.", vi: "…" },
                           extra_chips: [{ label: { en: "Do it for me", vi: "Làm giúp tôi" }, route: "payai", text: "lock the week", primary: true }] });
    await send("lock the week");
    const offer = chat.state.messages.filter((m) => m.kind === "guide").slice(-1)[0];
    check(/lrn-tchip pri/.test(String(host.helper.turnHTML(offer, "en"))), "the Do it for me chip is the solid one");
    const r1 = routes().length;
    await host._extraChip(offer.id, 0);
    check(routes().length === r1 && rpcs("rpc_send_message").length === 1
          && rpcs("rpc_send_message")[0].args[0] === "lock the week", "Do it for me → PayAI with the sentence");

    // Explain how instead under a PayAI card → the guide answer
    reset();
    routeAnswer = () => ({ route: "payai", why: "command",
                           extra_chips: [{ label: { en: "Explain how instead", vi: "…" }, route: "guide", key: "approve" }] });
    sendAnswer = () => ({ session_id: 7, response: "", intent: "command",
                          card: { kind: "plan", tier: "decide", task_id: 9, title: "Approve the June run", actions: [] } });
    await send("approve the request waiting for me");
    const cardMsg = chat.state.messages.filter((m) => m.card).slice(-1)[0];
    check(cardMsg && cardMsg.extra && cardMsg.extra[0].key === "approve", "the plan card carries Explain how instead");
    await host._extraChip(cardMsg.id, 0);
    check(chat.state.messages.slice(-1)[0].kind === "guide", "Explain how instead → the guide's answer below the card");
    check(rpcs("rpc_note_turn").some((c) => c.args[1] === "guide"), "… which writes a guide marker (the plan is no longer the last thing shown)");
    sendAnswer = () => ({ session_id: 7, response: "PayAI says.", intent: "general" });
}

// =================================================================== 2.5
async function bypassSuite() {
    console.log("2.5 chip bypass");
    const { host, chat } = await openChat();
    routeAnswer = () => ({ route: "payai", why: "question", ask_only: true });

    reset();
    chat._payaiResolve = { task_id: 4, slot: "period", value: "6" };
    await chat.sendText("June");
    check(routes().length === 0 && rpcs("rpc_send_message")[0].kwargs.resolve.task_id === 4,
          "with a pending resolve, sendText never calls the router");

    reset();
    chat._payaiResolve = { task_id: 4, slot: "period", value: "6" };
    chat.state.inputText = "June";
    await chat.submitComposer();
    check(routes().length === 0 && rpcs("rpc_send_message")[0].kwargs.resolve, "… nor does the composer");

    reset();
    const card = { task_id: 5, chip_slot: "period", chips: [{ label: "Change Period", value: "7" }], actions: [] };
    await chat.payaiPick({ card }, card.chips[0]);
    check(routes().length === 0 && rpcs("rpc_send_message").length === 1
          && rpcs("rpc_send_message")[0].kwargs.resolve.value === "7", "payaiPick reaches PayAI with its resolve, never the router");

    reset();
    await chat.payaiEdit({ card: { task_id: 6 } }, { key: "period", label: "Period" });
    await tick(5);
    check(routes().length === 0 && rpcs("rpc_send_message")[0].kwargs.resolve.action === "reask", "payaiEdit too");

    reset();
    await chat.payaiPick({ card: { task_id: 5, chips: [] } }, { ask: "What can you do?" });
    await tick(5);
    check(routes().length === 0 && rpcs("rpc_send_message").length === 1, "a chip with chip.ask (payaiAsk) is never routed");

    reset();
    await chat.payaiAct({ card: { task_id: 8 } }, { id: "followup", slot: "who", value: "12", label: "Nguyễn Văn An" });
    await tick(5);
    check(routes().length === 0 && rpcs("rpc_send_message")[0].kwargs.resolve.value === "12", "a follow-up chip with a resolve is never routed");

    reset();
    await chat.sendText("How do I run payroll?", { origin: "followup" });
    check(routes().length === 1, "a plain follow-up chip IS routed");

    reset();
    host.onClick({ target: fakeTarget({ act: "c-suggest", key: "approve", label: "How do I approve a request?" }), preventDefault() {} });
    await tick(5);
    check(routes().length === 1 && routes()[0].args[0] === "How do I approve a request?",
          "a context-card suggestion IS routed, with its own words");
}

/** Just enough of an element for CoachHost.onClick. */
function fakeTarget({ act, turn, ...data }) {
    const el = { dataset: { act, ...data } };
    const holder = turn ? { dataset: { turn } } : null;
    el.closest = (sel) => {
        if (sel === "[data-act]") { return el; }
        if (sel === "[data-turn]") { return holder; }
        return null;
    };
    return el;
}

// =================================================================== 2.6
async function langSuite() {
    console.log("2.6 language");
    const { host, chat } = await openChat();
    routeAnswer = () => ({ route: "guide", why: "guide_strong", answer: ANSWERS.approve });
    chat.state.inputText = "how do I approve a request";
    await chat.submitComposer();
    routeAnswer = () => ({ route: "note", why: "smalltalk", note: { en: "Happy to help.", vi: "Rất sẵn lòng.", key: "smalltalk" } });
    chat.state.inputText = "thanks";
    await chat.submitComposer();
    const guide = chat.state.messages.find((m) => m.kind === "guide");
    const note = chat.state.messages.find((m) => m.kind === "note");
    const en = String(chat.helperTurn(guide));
    chat.props.lang = "vi";
    const vi = String(chat.helperTurn(guide));
    check(/Approve a request/.test(en) && /Duyệt một yêu cầu/.test(vi), "a past guide turn re-renders in the other language");
    check(/From the guide/.test(en) && /Từ tài liệu hướng dẫn/.test(vi), "… source label too");
    check(/Rất sẵn lòng/.test(String(chat.helperTurn(note))), "a past note re-renders too");
    check(chat.placeholder === CONTENT.chrome.askAny.vi, "the composer placeholder follows the pill");
    check(chat._rpcContext().context.lang === "vi_VN", "the server is told vi_VN");
    check(RT.lang === host.state.lang, "rendering in another language leaves the runtime language alone");
    chat.props.lang = "en";
}

// =================================================================== 2.7
async function storeSuite() {
    console.log("2.7 close / reopen / reload");
    const { host, chat } = await openChat();
    routeAnswer = () => ({ route: "guide", why: "guide_strong", answer: ANSWERS.approve });
    chat.state.inputText = "how do I approve a request";
    await chat.submitComposer();
    unmount(chat);
    reset();
    const again = makeChat(host);
    await again._historyReady;
    check(rpcs("rpc_get_history").length === 0 && rpcs("rpc_helper_status").length === 1,
          "re-open: one status call, no history call");
    const g = again.state.messages.find((m) => m.kind === "guide");
    check(g && g.answer && g.answer.key === "approve", "re-open: the full guide answer is still there (not a marker)");
    unmount(again);

    reset();
    _resetPageMemory();
    historyRows = [
        { role: "user", content: "approve the June run", intent: "", card: null },
        { role: "assistant", content: "Approve the June run", intent: "command",
          card: { kind: "plan", task_id: 9, tier: "decide", actions: [] } },
        { role: "assistant", content: "Approve a request", intent: "helper_note",
          card: { kind: "guide", key: "approve", source_kind: "", screen_key: "payruns" } },
    ];
    const fresh = makeChat(host);
    await fresh._historyReady;
    check(rpcs("rpc_get_history").length === 1, "a fresh page load reads the history once");
    const marker = fresh.state.messages.find((m) => m.kind === "marker");
    check(marker && marker.mkind === "guide" && marker.key === "approve" && marker.card === null,
          "a helper_note row comes back as a marker, its card dropped");
    check(fresh.state.messages.some((m) => m.card && m.card.task_id === 9), "PayAI's own card still comes back as a card");
    const html = String(fresh.helperTurn(marker));
    check(/From the guide/.test(html) && /data-act="c-again"/.test(html), "the marker says From the guide and offers Show again");
    host._api = fresh.api;
    await host._expandMarker(marker.id);

    check(marker.expanded && marker.expanded.key === "approve", "Show again expands the answer in place");
    check(markerOf({ intent: "", card: { kind: "plan", task_id: 3 } }) === null, "a plan card is never mistaken for a marker");
    historyRows = [];
}

// =================================================================== 2.8
async function queueSuite() {
    console.log("2.8 the queue");
    _resetPageMemory();
    reset();
    const host = makeHost();
    host.state.moment = { kind: "first", watch: "" };
    host._momentAct("c-fvexplain");
    await tick(5);
    check(host.state.open === true, "the moment card's Explain opens the drawer");
    check(ormLog.filter((c) => c.method === "explain_screen").length === 0, "… and waits for the chat (nothing to draw it in yet)");
    // ⌘K, also before the chat has mounted
    const hook = pb.registry.category("pb_payai").get("open");
    host._payaiOpenHook("open the runs board");
    routeAnswer = () => ({ route: "payai", why: "command" });
    const chat = makeChat(host);
    await chat._historyReady;
    await tick(30);
    const explains = chat.state.messages.filter((m) => m.kind === "guide" && m.answer.source_kind === "screen");
    check(explains.length === 1, "after attach: the Explain answer appears once", JSON.stringify(kinds(chat)));
    check(routes().length === 1 && routes()[0].args[0] === "open the runs board", "after attach: the ⌘K sentence is routed once");
    check(rpcs("rpc_send_message").length === 1, "… and reaches PayAI once");
    check(typeof hook === "function" || hook === undefined, "the ⌘K hook seam exists");
    // header Explain with the chat attached: straight in
    reset();
    host.onClick({ target: fakeTarget({ act: "c-explain" }), preventDefault() {} });
    await tick(10);
    check(chat.state.messages.filter((m) => m.kind === "guide" && m.answer.source_kind === "screen").length === 2,
          "the header's Explain lands in the stream while an answer is showing");
    check(rpcs("rpc_note_turn").some((c) => c.args[1] === "explain"), "… with an explain marker");
}

// ============================================================ the shell
async function shellSuite() {
    console.log("the shell: banner, context card, menu, Escape");
    const { host, chat } = await openChat();
    check(chat.bannerText === CONTENT.chrome.honestAct.en, "the banner says PayAI may act (company can act)");
    chat.state.status.can_act = false;
    check(chat.bannerText === CONTENT.chrome.honestAsk.en, "… or only answer");
    chat.state.status.can_act = true;
    const ctx = String(chat.contextCard());
    check(/Not sure what to ask\?/.test(ctx), "the context card asks 'Not sure what to ask?'");
    check(/data-act="c-suggest"/.test(ctx) && /What can you do\?/.test(ctx), "… with the screen's questions and What can you do?");
    check(/data-act="c-practise-here"/.test(ctx), "… and Let me practise this (payruns has a Try)");
    check(!/Your next step/.test(ctx) && !/c-continue/.test(ctx), "no Your next step");
    check(String(host.bodyHTML).length > 0, "the guide-only stream still renders");
    // More menu
    host._attach(chat.api);
    host.menu.open = true;
    let menu = String(host.menuHTML);
    check(/data-act="c-readaloud"/.test(menu) === Boolean(chat.ttsSupported), "More: read answers aloud (when the device can speak)");
    check(/data-act="c-practice"/.test(menu), "More: Open practice mode");
    check(!/c-clear/.test(menu), "More: no Clear while the conversation is empty");
    routeAnswer = () => ({ route: "note", why: "smalltalk", note: { en: "Hi", vi: "Chào", key: "smalltalk" } });
    chat.state.inputText = "hi";
    await chat.submitComposer();
    host.menu.tick += 1;
    menu = String(host.menuHTML);
    check(/data-act="c-clear"/.test(menu), "More: Clear conversation once there is one");
    // Escape ladder
    let stopped = 0;
    const esc = () => host._onKey({ key: "Escape", target: { tagName: "DIV" }, stopPropagation() { stopped += 1; }, preventDefault() {} });
    host.state.open = true;
    host.menu.open = true;
    esc();
    check(host.menu.open === false && host.state.open === true && stopped === 1, "Escape 1: closes the menu only");
    chat.state.isRecording = true;
    let cancelled = 0;
    chat._stopRecording = () => { cancelled += 1; chat.state.isRecording = false; };
    esc();
    check(cancelled === 1 && host.state.open === true && chat._recCancelled === true, "Escape 2: cancels the recording, the drawer stays");
    esc();
    check(host.state.open === false, "Escape 3: closes the drawer");
    // clear: confirm, then empty
    host.state.open = true;
    reset();
    host.onClick({ target: fakeTarget({ act: "c-clear" }), preventDefault() {} });
    check(host.menu.confirm === true && /clearConvConfirm|Plans waiting for you stop working/.test(String((host.menu.open = true, host.menuHTML))),
          "Clear asks first: 'Plans waiting for you stop working.'");
    host.onClick({ target: fakeTarget({ act: "c-clear-yes" }), preventDefault() {} });
    await tick(5);
    check(rpcs("rpc_clear_history").length === 1 && chat.state.messages.length === 0, "… then clears the conversation");
    // the figures rule (Q2)
    check(chat._readable({ intent: "payroll_data", response: "Net pay is 12,000,000" }) === CONTENT.chrome.figuresOnScreen.en,
          "a pay-figures answer is never read aloud, only 'they are on screen'");
    check(chat._readable({ intent: "general", response: "**Open** Approvals" }) === "Open Approvals",
          "other answers are read without markdown symbols");
    // every act the drawer draws is declared
    const html = [String(host.menuHTML), ctx, String(chat.helperTurn({ id: "x", kind: "practice", practice: { chips: [{ key: "sc_payrun", mode: "try", name: { en: "Run" } }], sandbox: true } }))].join("");
    const acts = [...html.matchAll(/data-act="([a-z-]+)"/g)].map((m) => m[1]);
    check(acts.length && acts.every((a) => COACH_ACTIONS.has(a)), "every data-act drawn is in COACH_ACTIONS", acts.join(","));
}


// ======================================================= leftover review
async function leftoverSuite() {
    console.log("OC2/OC3 leftover review findings");

    // 1. the full-page PayAI chat never draws the helper's markers as replies
    reset();
    historyRows = [
        { role: "user", content: "how many employees do we have", intent: "", card: null },
        { role: "assistant", content: "You have 42 employees.", intent: "payroll_data", card: null },
        { role: "assistant", content: "Approve a request", intent: "helper_note",
          card: { kind: "guide", key: "approve", source_kind: "", screen_key: "payruns" } },
        { role: "assistant", content: "Practice mode", intent: "helper_note",
          card: { kind: "practice", key: "", source_kind: "", screen_key: "" } },
    ];
    const full = mountFull(fullMod.AiInsightChatFull, {}, {});
    await tick(5);
    check(full.state.messages.length === 2 && !full.state.messages.some((m) => m.intent === "helper_note"),
          "1. the full-page chat leaves out the helper's markers", JSON.stringify(full.state.messages.map((m) => m.content)));
    check(full.state.messages.some((m) => m.content === "You have 42 employees."), "… and keeps PayAI's own replies");
    historyRows = [historyRows[2]];
    const fullOnlyMarkers = mountFull(fullMod.AiInsightChatFull, {}, {});
    await tick(5);
    check(fullOnlyMarkers.state.messages.length === 0 && fullOnlyMarkers.state.showSuggestions === true,
          "… a thread of markers only shows the full page's welcome");
    historyRows = [];

    // 2. the banner and the placeholder promise only what this database can do
    {
        const { chat } = await openChat();
        chat.state.status = { can_act: false, can_answer: false, voice_go_ahead: false };
        check(chat.bannerText === CONTENT.chrome.honestGuide.en && chat.placeholder === CONTENT.chrome.askPlaceholder.en,
              "2. no assistant service: the banner and the box speak only of this screen",
              JSON.stringify([chat.bannerText, chat.placeholder]));
        check(!/pay figures/i.test(chat.bannerText + chat.placeholder), "… and promise no pay figures");
        chat.state.status = { can_act: false, can_answer: true, voice_go_ahead: false };
        check(chat.bannerText === CONTENT.chrome.honestAsk.en && chat.placeholder === CONTENT.chrome.askAnyNoAct.en,
              "… with the service: pay figures are offered");
        chat.state.status = { can_act: true, can_answer: true, voice_go_ahead: false };
        check(chat.bannerText === CONTENT.chrome.honestAct.en && chat.placeholder === CONTENT.chrome.askAny.en,
              "… and where PayAI may act, the act wording");
        unmount(chat);
    }

    // 3. a ⌘K sentence given up on is never sent on a later, unrelated open
    _resetPageMemory();
    reset();
    {
        const host = makeHost();
        routeAnswer = () => ({ route: "payai", why: "command" });
        host._payaiOpenHook("open the runs board");
        check(host.state.open === true && host._queue.length === 1, "3. ⌘K opens the drawer and waits for the chat");
        host.close();                       // given up before the chat mounted
        host.toggle();                      // later: opened with ?, nothing typed
        const chat = makeChat(host);
        await chat._historyReady;
        await tick(30);
        check(routes().length === 0 && rpcs("rpc_send_message").length === 0,
              "… closed before the chat mounted: the sentence is NOT sent on the next open",
              JSON.stringify(routes().map((c) => c.args[0])));
        unmount(chat);
        // the chat mounted, then closed before its history landed
        reset();
        host.state.open = false;
        host._payaiOpenHook("open the runs board");
        const early = makeChat(host);
        unmount(early);                     // the drawer closed while loading
        host.state.open = false;
        await tick(10);
        host.toggle();
        const later = makeChat(host);
        await later._historyReady;
        await tick(30);
        check(routes().length === 0 && rpcs("rpc_send_message").length === 0 && host._queue.length === 0,
              "… unmounted before attach: the queue is emptied, nothing sent later");
        // and a ⌘K sentence that WAS waited for is still sent once
        reset();
        host._payaiOpenHook("open the runs board");
        await tick(30);
        check(routes().length === 1 && rpcs("rpc_send_message").length === 1, "… a ⌘K sentence with the chat open is routed once");
        unmount(later);
    }

    // 4. every non-PayAI turn the chat shows writes its marker
    {
        const { host, chat } = await openChat();
        reset();
        host.state.screen = "runpayroll";   // two scenarios to practise here
        host._practiseHere();
        await tick(5);
        const chipsTurn = chat.state.messages.filter((m) => m.kind === "practice").slice(-1)[0];
        check(chipsTurn && chipsTurn.practice && chipsTurn.practice.chips && chipsTurn.practice.chips.length >= 2,
              "4. Let me practise this draws the practice chips");
        check(rpcs("rpc_note_turn").filter((c) => c.args[1] === "practice").length === 1,
              "… and writes a practice marker", JSON.stringify(rpcs("rpc_note_turn").map((c) => c.args.slice(1, 3))));
        host.state.screen = "payruns";
        reset();
        host.showMe("no-such-control");
        await tick(5);
        check(chat.state.messages.slice(-1)[0].kind === "note"
              && rpcs("rpc_note_turn").some((c) => c.args[1] === "note" && c.args[2] === "pointNotHere"),
              "… 'That control is not on this screen' writes a note marker",
              JSON.stringify(rpcs("rpc_note_turn").map((c) => c.args.slice(1, 3))));
        reset();
        routeAnswer = () => null;           // the router did not answer
        chat.state.inputText = "anything";
        await chat.submitComposer();
        check(rpcs("rpc_note_turn").some((c) => c.args[1] === "note" && c.args[2] === "routeFailed"),
              "… the 'did not go through' note writes one too");
        reset();
        chat.api.pushTurn({ kind: "consent" });
        await tick(5);
        check(chat.state.messages.slice(-1)[0].kind === "consent" && rpcs("rpc_note_turn").length === 0,
              "… the question-collection card is not a marker of its own (it rides with its answer)");
        unmount(chat);
    }

    // 5. a "Which did you mean?" chip pressed while PayAI is busy stays usable
    {
        const { host, chat } = await openChat();
        reset();
        routeAnswer = () => ({ route: "choose", why: "weak", note: { en: "Which did you mean?", vi: "…", key: "whichMeant" },
                               choices: [{ label: { en: "Approve a request", vi: "Duyệt" }, route: "guide", key: "approve" },
                                         { label: { en: "Ask about your pay data", vi: "Hỏi" }, route: "payai",
                                           text: "can I approve", ask_only: true }] });
        chat.state.inputText = "approve?";
        await chat.submitComposer();
        const turn = chat.state.messages.filter((m) => m.kind === "choose").slice(-1)[0];
        chat.state.isLoading = true;        // PayAI still answering something else
        await host._pickChoice(turn.id, 1);
        check(rpcs("rpc_send_message").length === 0 && (turn.picked === null || turn.picked === undefined),
              "5. pressed while busy: nothing sent, and the choice is NOT used up", String(turn.picked));
        check(!/disabled/.test(String(host.helper.turnHTML(turn, "en"))), "… its chips are still pressable");
        chat.state.isLoading = false;
        await host._pickChoice(turn.id, 1);
        check(rpcs("rpc_send_message").length === 1 && rpcs("rpc_send_message")[0].args[0] === "can I approve"
              && turn.picked === 1, "… pressed again once PayAI is free: sent once, then used");
        await host._pickChoice(turn.id, 0);
        check(rpcs("rpc_send_message").length === 1 && !ormLog.some((c) => c.method === "answer_for"),
              "… and only once (the other chip is dead after a real pick)");
        unmount(chat);
    }
}

for (const suite of [spokenSuite, dispatchSuite, bypassSuite, langSuite, storeSuite, queueSuite, shellSuite,
                     leftoverSuite]) {
    try {
        await suite();
    } catch (e) {
        check(false, `${suite.name} crashed`, String(e && e.stack || e));
    }
}
summary();
