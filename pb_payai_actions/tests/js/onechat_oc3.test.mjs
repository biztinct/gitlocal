/**
 * ONECHAT OC3 — voice in the one chat, run in node (no browser).
 *
 * The real embedded chat (pb_payroll_ai_insights ai_insight_chat.js), the
 * real drawer (pb_learn coach.js) and the real PayAI patch (chat_patch.js),
 * wired as the browser wires them; the server, the microphone, the recorder,
 * Web Audio and the device's speech are fakes this file controls.
 *
 *   3.4  tap to talk: Starting… then Listening only after `onstart`; a stop
 *        before the start is applied when it starts; a recorder that fails
 *        to build gives the microphone back; the format fallback order; the
 *        meter's audio context closed inside `_releaseMicrophone`, after the
 *        tracks; a short and a silent recording are never uploaded; filler
 *        and the echoed hint never reach the box; Escape cancels and leaves
 *        the drawer open; close mid-recording sends nothing; "Hear it as …";
 *        hold past 400 ms stops on release; Space / Enter toggle
 *   3.5  read-back: a mic tap stops speech; the voice follows the text's
 *        language; the brand filter; figures and amounts never read (Q2);
 *        a spoken turn is read, a typed one only with Read aloud on; no
 *        Vietnamese voice → nothing read, said once; the Stop control
 *   + the words wait for Send (Q1): no route, no send until Send
 *
 * Run: node pb_payai_actions/tests/js/onechat_oc3.test.mjs   (exit 1 on failure)
 */
import fs from "node:fs";
import path from "node:path";
import { check, load, summary, ROOT } from "./harness.mjs";

const pb = globalThis.__pb;
const noop = () => {};
const tick = (ms = 0) => new Promise((r) => setTimeout(r, ms));
/** Wait (real time, at most 2 s) until `ok()` — never on a guessed delay. */
async function until(ok) {
    for (let i = 0; i < 400 && !ok(); i++) { await tick(5); }
    return ok();
}
const listening = (chat) => until(() => chat.state.isRecording);

// ---------------------------------------------------------------- the clock
let clock = 1_000_000;
const realNow = Date.now;
Date.now = () => clock;

// ---------------------------------------------------------- the device
const speech = { spoken: [], cancels: 0, voices: [], listeners: {} };
class FakeUtterance {
    constructor(text) { this.text = text; this.lang = ""; this.voice = null; }
}
const synth = {
    speak(u) { speech.spoken.push(u); },
    cancel() { speech.cancels += 1; },
    getVoices() { return speech.voices; },
    addEventListener(name, fn) { speech.listeners[name] = fn; },
    removeEventListener(name) { delete speech.listeners[name]; },
};
const EN_VOICE = { lang: "en-US", name: "Samantha" };
const VI_VOICE = { lang: "vi-VN", name: "Linh" };

const audio = { level: 0, contexts: [], log: [] };
class FakeAudioContext {
    constructor() { this.closed = false; audio.contexts.push(this); }
    createAnalyser() {
        return {
            fftSize: 512,
            getByteTimeDomainData(buf) {
                for (let i = 0; i < buf.length; i++) {
                    buf[i] = 128 + Math.round((i % 2 ? 1 : -1) * audio.level * 127);
                }
            },
        };
    }
    createMediaStreamSource() { return { connect: noop }; }
    close() { this.closed = true; audio.log.push("context.close"); return Promise.resolve(); }
}

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
    speechSynthesis: synth,
    SpeechSynthesisUtterance: FakeUtterance,
    AudioContext: FakeAudioContext,
};

// The microphone and the recorder.
const mic = { grants: 0, streams: [], deny: null, pending: null, supported: ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"] };
function makeStream() {
    const track = { stopped: false, stop() { this.stopped = true; audio.log.push("track.stop"); } };
    const stream = { track, getTracks: () => [track] };
    mic.streams.push(stream);
    return stream;
}
Object.defineProperty(globalThis, "navigator", {
    configurable: true,
    value: {
        mediaDevices: {
            getUserMedia: () => {
                mic.grants += 1;
                if (mic.deny) {
                    const err = new Error("denied");
                    err.name = mic.deny;
                    return Promise.reject(err);
                }
                if (mic.pending) {
                    return mic.pending.promise;
                }
                return Promise.resolve(makeStream());
            },
        },
    },
});
let recorders = [];
let recorderThrows = false;
let autoStart = true;
class FakeRecorder {
    static isTypeSupported(type) { return mic.supported.includes(type); }
    constructor(stream, opts) {
        if (recorderThrows) { throw new Error("cannot record"); }
        this.stream = stream;
        this.mimeType = opts && opts.mimeType;
        this.state = "inactive";
        recorders.push(this);
    }
    start() {
        this.state = "recording";
        if (autoStart) { setTimeout(() => this.fireStart(), 0); }
    }
    fireStart() { if (this.onstart) { this.onstart(); } }
    stop() {
        this.state = "inactive";
        setTimeout(() => {
            if (this.ondataavailable) { this.ondataavailable({ data: new Blob(["voice-bytes"]) }); }
            if (this.onstop) { this.onstop(); }
        }, 0);
    }
}
globalThis.MediaRecorder = FakeRecorder;

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

// ---------------------------------------------------------------- the server
let rpcLog = [];
let ormLog = [];
let transcripts = [];       // what the service "hears", one per call
let routeAnswer = () => ({ route: "note", why: "smalltalk", note: { en: "Happy to help.", vi: "Rất sẵn lòng.", key: "smalltalk" } });
let sendAnswer = () => ({ session_id: 7, response: "PayAI answers.", intent: "general" });
const VOCAB = {
    en: "Payobook, pay run, payslip, pay scheme, overtime, BHXH, BHYT, BHTN",
    vi: "Payobook, đợt lương, phiếu lương, chương trình lương, tăng ca, BHXH, BHYT, BHTN",
};
const VOICE_ON = { available: true, ask: false, consent: "granted", switch_on: true, provider_ready: true,
                   vocab: VOCAB, copy: { check_hint: "This is what I heard. Edit it, then press send.",
                                         tap_hint: "Tap to speak", failed: "I could not turn that into text." } };
pb.rpc = async (_route, params) => {
    const { method, args, kwargs } = params;
    rpcLog.push({ method, args, kwargs });
    if (method === "rpc_helper_status") {
        return { session_id: 7, voice: VOICE_ON, can_answer: true, can_act: true, voice_go_ahead: false, icon_url: false };
    }
    if (method === "rpc_get_history") { return { session_id: 7, messages: [] }; }
    if (method === "rpc_send_message") { return sendAnswer(args, kwargs); }
    if (method === "rpc_note_turn") { return { session_id: 7, message_id: rpcLog.length }; }
    if (method === "rpc_register_doors") { return { session_id: 7 }; }
    if (method === "rpc_transcribe_voice") { return { text: transcripts.length ? transcripts.shift() : "" }; }
    return null;
};
const ANSWERS = {
    howrun: { key: "howrun", matched: true, label: { en: "Run payroll", vi: "Chạy lương" },
              blocks: [{ kind: "p", body: { en: "Open <b>Pay Run</b> and press Run.", vi: "Mở <b>Đợt lương</b> rồi bấm Chạy." } },
                       { kind: "source", body: { en: "Grounded in the Pay Run lesson", vi: "Dựa trên bài Đợt lương" } }],
              watch: "", try: "", show_me: [], simpler: "" },
};
const orm = {
    call: async (model, method, args = [], kwargs = {}) => {
        ormLog.push({ model, method, args, kwargs });
        if (model === "learn.helper" && method === "route") { return routeAnswer(args[0], kwargs); }
        if (method === "answer_for") { return ANSWERS[args[0]] || { matched: false, suggest: [] }; }
        if (method === "log") { return true; }
        return null;
    },
};
const sc = { state: {}, get: () => null, forScreen: () => [], load: async () => {}, begin: async () => true, steps: () => [] };
pb.services.orm = orm;
pb.services.action = { currentController: null, doAction: async () => {} };
pb.services["learn.scenario"] = sc;
pb.services.notification = { add: noop };
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
const { RT } = runtime;
const { CoachHost } = coachMod;
const { AiInsightChat, AiInsightChatEmbedded, _resetPageMemory, pickRecordingType,
        isPhantomTranscript, speechText, pickVoice } = chatMod;
RT.chrome = CONTENT.chrome;
RT.lang = "en";
const chatPatch = pb.patches.find((p) => p.target === AiInsightChat.prototype && typeof p.obj._payaiRegisterDoors === "function");
const hostPatch = pb.patches.find((p) => p.target === CoachHost.prototype);
Object.setPrototypeOf(AiInsightChatEmbedded.prototype, chatPatch.obj);
class Host extends CoachHost {}
Object.setPrototypeOf(Host.prototype, hostPatch.obj);
const C = (key, lang = "en") => CONTENT.chrome[key][lang];

function makeHost() {
    const host = mountFull(Host, {}, { bus: {} });
    host.place = { tag: "", lens: "", subs: {}, lenses: [], seq: 0, detail: "", ready: true };
    host.chatAllowed = true;
    host.bundle = {
        screens: [{ key: "payruns", name: { en: "Pay runs", vi: "Các đợt lương" },
                    blurb: { en: "Every pay run.", vi: "Mọi đợt lương." }, suggest: [] }],
        global_suggest: [], chrome: CONTENT.chrome, collect_questions: false,
    };
    host.state.ready = true;
    host.state.screen = "payruns";
    return host;
}
const box = { focused: 0, value: "", selectionStart: 0, selectionEnd: 0, style: {},
              focus() { this.focused += 1; } };
async function openChat(lang = "en") {
    _resetPageMemory();
    const host = makeHost();
    host.state.open = true;
    host.state.lang = lang;
    const chat = mountFull(AiInsightChatEmbedded,
        { helper: host.helper, lang, screen: "payruns", place: "", close: noop },
        { services: { orm, pb_hub_palette: null } });
    chat.inputRef.el = box;
    await chat._historyReady;
    await tick(5);
    host._attach(chat.api);
    return { host, chat };
}
function reset() {
    rpcLog = [];
    ormLog = [];
    transcripts = [];
    recorders = [];
    recorderThrows = false;
    autoStart = true;
    mic.deny = null;
    mic.pending = null;
    mic.grants = 0;
    mic.supported = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
    audio.level = 0.3;
    audio.contexts = [];
    audio.log = [];
    speech.spoken = [];
    speech.cancels = 0;
    speech.voices = [EN_VOICE, VI_VOICE];
    box.focused = 0;
}
const tap = (chat) => chat.onMicPointerDown({ button: 0 });
const lift = (chat) => chat.onMicPointerUp({});
/** Tap, wait for the recorder to really start, talk for `ms`, tap Stop. */
async function record(chat, ms = 1500, words = "how do I run payroll") {
    transcripts.push(words);
    const before = rpcs("rpc_transcribe_voice").length;
    tap(chat);
    lift(chat);
    await listening(chat);
    await tick(100);           // the meter reads while it listens
    clock += ms;
    tap(chat);
    lift(chat);
    await until(() => !chat.state.isRecording);
    await tick(15);
    await until(() => !chat.state.voiceBusy);
    await tick(5);
    return rpcs("rpc_transcribe_voice").length > before;
}

// =================================================================== 3.4
async function recorderSuite() {
    console.log("3.4 tap to talk — the recorder");

    // the format fallback order
    reset();
    check(pickRecordingType() === "audio/webm;codecs=opus", "format: WebM/Opus first");
    mic.supported = ["audio/webm", "audio/mp4"];
    check(pickRecordingType() === "audio/webm", "… then WebM");
    mic.supported = ["audio/mp4"];
    check(pickRecordingType() === "audio/mp4", "… then MP4 (Safari, iOS)");
    mic.supported = [];
    check(pickRecordingType() === null, "… none → null");
    {
        const { chat } = await openChat();
        check(!chat.voiceOffered && chat.voiceUnsupported, "no format: the microphone is not drawn");
        check(chat.state.voiceHint === C("micUnsupported"), "… and the hint says the browser cannot record here",
              chat.state.voiceHint);
        unmount(chat);
    }

    // Starting… then Listening, only after onstart
    reset();
    {
        const { chat } = await openChat();
        check(chat.voiceOffered, "voice on + a recording browser: one microphone");
        autoStart = false;
        tap(chat);
        lift(chat);
        await tick(2);
        check(chat.state.micStarting && !chat.state.isRecording, "tap → 'Starting…', not yet 'Listening'");
        check(recorders.length === 1 && recorders[0].mimeType === "audio/webm;codecs=opus", "the recorder is built with the chosen format");
        recorders[0].fireStart();
        check(chat.state.isRecording && !chat.state.micStarting, "onstart → 'Listening'");
        check(chat.recordingClock === "0:00 / 1:00", "the clock reads 0:00 / 1:00", chat.recordingClock);
        await tick(100);
        check(chat.levelBars.length === 5 && chat.levelBars.some((b) => b > 18), "five live level bars move", JSON.stringify(chat.levelBars));
        // a quick tap leaves it running; the next tap stops it
        clock += 1500;
        tap(chat);
        lift(chat);
        await tick(15);
        await until(() => rpcs("rpc_transcribe_voice").length > 0);
        check(!chat.state.isRecording && recorders[0].state === "inactive", "the second tap is Stop");
        check(rpcs("rpc_transcribe_voice").length === 1, "Stop → the recording goes to be turned into text, once");
        const call = rpcs("rpc_transcribe_voice")[0];
        check(call && call.kwargs.lang === null && call.kwargs.mime === "audio/webm",
              "auto-detect (lang null) and the real format travel with it", JSON.stringify(call && call.kwargs));
        unmount(chat);
    }

    // stop before start: applied the moment it starts
    reset();
    {
        const { chat } = await openChat();
        let grant;
        mic.pending = { promise: new Promise((r) => { grant = r; }) };
        autoStart = false;
        tap(chat);
        lift(chat);
        await tick(2);
        tap(chat);                    // Stop while the browser still asks
        lift(chat);
        check(chat._stopWanted === true, "Stop during the permission question is remembered");
        grant(makeStream());
        await tick(2);
        check(recorders.length === 1 && recorders[0].state === "recording", "the recorder starts once allowed");
        recorders[0].fireStart();
        check(recorders[0].state === "inactive", "… and stops the moment it starts (no silent minute)");
        await tick(15);
        check(rpcs("rpc_transcribe_voice").length === 0, "a recording that never ran is not uploaded");
        check(mic.streams.slice(-1)[0].track.stopped, "the microphone is given back");
        unmount(chat);
    }

    // a recorder that fails to build releases the stream
    reset();
    {
        const { chat } = await openChat();
        recorderThrows = true;
        tap(chat);
        lift(chat);
        await tick(5);
        check(mic.streams.slice(-1)[0].track.stopped, "MediaRecorder throws → the stream's tracks are stopped");
        check(!chat.state.micStarting && !chat.state.isRecording, "… and the bar is gone");
        check(chat.state.voiceError === C("micCannot"), "… 'This browser could not start the microphone.'", chat.state.voiceError);
        recorderThrows = false;
        mic.deny = "NotAllowedError";
        tap(chat);
        lift(chat);
        await tick(5);
        check(chat.state.voiceError === C("micDenied"), "NotAllowedError → 'Microphone access is blocked…'", chat.state.voiceError);
        unmount(chat);
    }

    // the audio context closes inside _releaseMicrophone, after the tracks
    reset();
    {
        const { chat } = await openChat();
        await record(chat, 1500);
        const iTrack = audio.log.indexOf("track.stop");
        const iCtx = audio.log.indexOf("context.close");
        check(iTrack >= 0 && iCtx > iTrack, "the level meter's audio context is closed after the tracks stop", audio.log.join(","));
        const src = chat._releaseMicrophone.toString();
        check(src.indexOf("getTracks") < src.indexOf(".close()"), "… inside _releaseMicrophone, in that order");
        unmount(chat);
    }

    // a short recording and a silent one are not uploaded
    reset();
    {
        const { chat } = await openChat();
        await record(chat, 400);
        check(rpcs("rpc_transcribe_voice").length === 0, "a 400 ms recording is not uploaded");
        check(chat.state.voiceHint === C("heardNothing"), "… 'I didn't hear anything…'", chat.state.voiceHint);
        audio.level = 0;
        await record(chat, 3000);
        check(rpcs("rpc_transcribe_voice").length === 0, "a silent recording is not uploaded");
        audio.level = 0.3;
        unmount(chat);
    }

    // filler and the echoed hint never reach the box
    reset();
    {
        const { chat } = await openChat();
        for (const said of ["Thank you for watching.", "Thanks for watching!", "Cảm ơn các bạn đã xem",
                            "Payobook, pay run, payslip, pay scheme, overtime"]) {
            chat.state.inputText = "";
            await record(chat, 1500, said);
            check(chat.state.inputText === "" && chat.state.voiceHint === C("heardNothing"),
                  `"${said}" is dropped`, chat.state.inputText);
        }
        check(!isPhantomTranscript("go ahead", VOCAB) && !isPhantomTranscript("chạy lương thế nào", VOCAB)
              && !isPhantomTranscript("thank you", VOCAB),
              "real sentences pass (go ahead, chạy lương thế nào, thank you)");
        unmount(chat);
    }

    // the words land in the box and wait for Send (Q1)
    reset();
    {
        const { chat } = await openChat();
        chat.state.inputText = "";
        await record(chat, 1500, "how do I run payroll");
        await tick(2);
        check(chat.state.inputText === "how do I run payroll", "the words land in the box");
        check(routes().length === 0 && rpcs("rpc_send_message").length === 0, "… and nothing is routed or sent until Send");
        check(box.focused > 0, "focus goes to the box (cursor at the end), never to Send");
        check(chat.state.hearAs === "vi", "'Hear it as Tiếng Việt' is offered for an English hearing");
        // Hear it as Tiếng Việt: the SAME recording, lang vi, replaces the words
        transcripts.push("chạy lương thế nào");
        await chat.hearAs("vi");
        const again = rpcs("rpc_transcribe_voice").slice(-1)[0];
        check(again && again.kwargs.lang === "vi" && again.args[0] === rpcs("rpc_transcribe_voice")[0].args[0],
              "Hear it as … re-sends the same audio with lang=vi");
        check(chat.state.inputText === "chạy lương thế nào" && chat.state.hearAs === "en",
              "… the box now holds the Vietnamese words; 'Hear it as English' is offered", chat.state.inputText);
        check(chat._takeSpoken.call({ _heard: chat._heard }, chat.state.inputText) === true,
              "… still spoken (untouched, heard into an empty box)");
        routeAnswer = () => ({ route: "guide", why: "guide_strong", answer: ANSWERS.howrun });
        await chat.submitComposer();
        check(routes().length === 1 && chat._keptAudio === null && chat.state.hearAs === null,
              "Send routes it once and drops the kept recording",
              JSON.stringify({ routes: routes().length, kept: !!chat._keptAudio, hearAs: chat.state.hearAs }));
        unmount(chat);
    }

    // Escape while recording cancels and leaves the drawer open; close sends nothing
    reset();
    {
        const { host, chat } = await openChat();
        tap(chat);
        lift(chat);
        await listening(chat);
        clock += 2000;
        let stopped = 0;
        host._onKey({ key: "Escape", target: { tagName: "DIV" }, stopPropagation() { stopped += 1; }, preventDefault: noop });
        await tick(15);
        check(host.state.open === true && stopped === 1, "Escape while recording: the drawer stays open");
        check(rpcs("rpc_transcribe_voice").length === 0 && !chat.state.isRecording, "… the recording is cancelled, nothing uploaded");
        // Escape during 'Starting…' cancels too
        autoStart = false;
        tap(chat);
        lift(chat);
        await tick(2);
        host._onKey({ key: "Escape", target: { tagName: "DIV" }, stopPropagation: noop, preventDefault: noop });
        recorders.slice(-1)[0].fireStart();
        await tick(15);
        check(host.state.open === true && rpcs("rpc_transcribe_voice").length === 0, "Escape during 'Starting…' cancels before anything records");
        autoStart = true;
        // close mid-recording
        tap(chat);
        lift(chat);
        await listening(chat);
        clock += 2000;
        unmount(chat);
        await tick(15);
        check(rpcs("rpc_transcribe_voice").length === 0, "closing the drawer mid-recording sends nothing");
        check(mic.streams.every((s) => s.track.stopped), "… and every microphone stream is stopped");
    }

    // press-and-hold, the keyboard, Cancel, the ceiling
    reset();
    {
        const { chat } = await openChat();
        transcripts.push("go ahead");
        tap(chat);
        await listening(chat);
        await tick(100);
        clock += 900;              // held 900 ms
        lift(chat);
        await tick(15);
        await until(() => !chat.state.voiceBusy);
        check(rpcs("rpc_transcribe_voice").length === 1, "a press held past 400 ms stops on release");
        chat.state.inputText = "";
        const key = (k, repeat = false) => ({ key: k, repeat, preventDefault: noop });
        transcripts.push("approve");
        chat.onMicKeyDown(key(" "));
        chat.onMicKeyDown(key(" ", true));        // key repeat: ignored
        chat.onMicKeyUp(key(" "));
        await listening(chat);
        check(chat.state.isRecording && recorders.length === 2, "Space on the microphone starts it (key repeat ignored)",
              String(recorders.length));
        await tick(100);
        clock += 1500;
        chat.onMicKeyDown(key("Enter"));
        chat.onMicKeyUp(key("Enter"));
        await tick(15);
        await until(() => !chat.state.voiceBusy);
        check(!chat.state.isRecording && rpcs("rpc_transcribe_voice").length === 2, "Enter stops it");
        // Cancel
        tap(chat);
        lift(chat);
        await listening(chat);
        clock += 2000;
        chat.cancelRecording();
        await tick(15);
        check(rpcs("rpc_transcribe_voice").length === 2, "Cancel sends nothing");
        // the 60-second ceiling
        tap(chat);
        lift(chat);
        await listening(chat);
        chat.state.recordingDuration = 59;
        clock += 60_000;
        await new Promise((r) => setTimeout(r, 1100));
        await tick(15);
        check(!chat.state.isRecording, "the 60-second ceiling stops the recorder");
        unmount(chat);
    }
}

// =================================================================== 3.5
async function readBackSuite() {
    console.log("3.5 read-back");
    reset();
    const { chat } = await openChat();

    // a mic tap cancels speech; nothing is read while recording
    const before = speech.cancels;
    tap(chat);
    lift(chat);
    await listening(chat);
    check(speech.cancels > before, "a microphone tap stops anything being read");
    const n = speech.spoken.length;
    chat.speak("Hello there");
    check(speech.spoken.length === n, "nothing is read aloud while the microphone is open");
    chat.cancelRecording();
    await tick(15);

    // the voice follows the text
    speech.spoken = [];
    chat.speak("Bấm Chạy để chạy lương.");
    chat.speak("Press Run.");
    check(speech.spoken[0].lang === "vi-VN" && speech.spoken[0].voice === VI_VOICE, "Vietnamese marks → a vi-VN voice");
    check(speech.spoken[1].lang === "en-US" && speech.spoken[1].voice === EN_VOICE, "otherwise en-US");
    check(pickVoice([{ lang: "vi_VN" }], "vi-VN") !== null, "voice lists written vi_VN are found too");

    // brand filter and amounts (Q2)
    check(!/odoo/i.test(speechText("Open the Odoo settings")), "the vendor's name is never spoken", speechText("Open the Odoo settings"));
    const plan = speechText("I will change Meal allowance for Payai Linh Nguyen to 500,000. Tap Do it to go ahead.");
    check(!/500/.test(plan) && /an amount shown on screen/.test(plan) && /Payai Linh Nguyen/.test(plan),
          "a plan's amount is not read; the name and the rest are", plan);
    const month = speechText("I will run June 2031 payroll for Retail, 3 people.");
    check(month === "I will run June 2031 payroll for Retail, 3 people.", "years and small counts are not amounts", month);
    check(!/\d{3}/.test(speechText("Lương 12.000.000 VND, 5 triệu đồng, $1,200, 1500000")), "VND, triệu, $ and long numbers are not read");
    check(speechText("x".repeat(900)).length <= 600, "at most 600 characters are read");
    speech.spoken = [];
    chat.speak("Net pay is 12,000,000 for June.");
    check(speech.spoken.length === 1 && !/12/.test(speech.spoken[0].text), "speak() itself never reads an amount", speech.spoken[0] && speech.spoken[0].text);
    check(chat._readable({ intent: "payroll_data", response: "Lan's net pay is 12,000,000" }) === C("figuresOnScreen"),
          "a pay-figures answer reads only 'they are on screen'");

    // spoken turns are read; typed ones only with Read aloud on
    chat.state.ttsOn = false;
    routeAnswer = () => ({ route: "guide", why: "guide_strong", answer: ANSWERS.howrun });
    speech.spoken = [];
    chat._heard = null;
    chat.state.inputText = "how do I run payroll";
    await chat.submitComposer();
    check(speech.spoken.length === 0, "a typed guide answer is not read (Read aloud off)");
    chat.state.inputText = "";
    await record(chat, 1500, "how do I run payroll");
    await chat.submitComposer();
    const read = speech.spoken.slice(-1)[0];
    check(read && /Run payroll/.test(read.text) && /press Run/.test(read.text), "a SPOKEN guide question is read back", read && read.text);
    check(read && !/Grounded in/.test(read.text) && !/<b>/.test(read.text), "… without the source line or markup");
    const turn = chat.state.messages.filter((m) => m.kind === "guide").slice(-1)[0];
    check(turn && chat.state.speakingId === turn.id, "the turn being read carries the Stop control");
    chat.stopReading();
    check(chat.state.speakingId === null, "Stop reading clears it");
    chat.state.ttsOn = true;
    speech.spoken = [];
    chat.state.inputText = "how do I run payroll";
    await chat.submitComposer();
    check(speech.spoken.length === 1, "a typed answer is read when Read aloud is on");
    chat.state.ttsOn = false;
    // PayAI data answer, spoken
    routeAnswer = () => ({ route: "payai", why: "data", ask_only: true });
    sendAnswer = () => ({ session_id: 7, response: "There are 152 employees, total 1,250,000,000.", intent: "payroll_data" });
    speech.spoken = [];
    chat.state.inputText = "";
    await record(chat, 1500, "how many employees do we have");
    await chat.submitComposer();
    check(speech.spoken.length === 1 && speech.spoken[0].text === C("figuresOnScreen"),
          "a spoken pay-data question is answered aloud with 'the figures are on screen' only", speech.spoken[0] && speech.spoken[0].text);
    check(rpcs("rpc_send_message").slice(-1)[0].kwargs.voice === true, "… and PayAI was told it was spoken");
    // a spoken plan: its own read-back (card.speak), not the summary
    routeAnswer = () => ({ route: "payai", why: "command" });
    sendAnswer = () => ({ session_id: 7, response: "Run payroll", intent: "command",
                          card: { kind: "plan", task_id: 41, tier: "prepare", title: "Run payroll",
                                  speak: "I will run June 2031 payroll for Retail, 3 people. Tap Do it to go ahead." } });
    speech.spoken = [];
    chat.state.inputText = "";
    await record(chat, 1500, "run June payroll for Retail");
    await chat.submitComposer();
    check(speech.spoken.length === 1 && /I will run June 2031 payroll/.test(speech.spoken[0].text),
          "a spoken plan reads its own read-back once", JSON.stringify(speech.spoken.map((u) => u.text)));
    // new typing stops speech
    const c0 = speech.cancels;
    chat.onInputChange({ target: { value: "x" } });
    check(speech.cancels > c0, "new typing stops the reading");

    // no Vietnamese voice: nothing read, said once
    speech.voices = [EN_VOICE];
    speech.spoken = [];
    chat.state.voiceHint = "";
    chat.speak("Bấm Chạy để chạy lương.");
    check(speech.spoken.length === 0 && chat.state.voiceHint === C("noViVoice"), "no Vietnamese voice → nothing read, and it says so");
    chat.state.voiceHint = "";
    chat.speak("Mở Đợt lương.");
    check(chat.state.voiceHint === "", "… only once");
    // voices that load late
    speech.voices = [];
    speech.spoken = [];
    chat.speak("Press Run.");
    check(speech.spoken.length === 0 && typeof speech.listeners.voiceschanged === "function", "voices not loaded yet: waits for voiceschanged");
    speech.voices = [EN_VOICE];
    speech.listeners.voiceschanged();
    check(speech.spoken.length === 1 && speech.spoken[0].voice === EN_VOICE, "… then reads with the right voice");
    unmount(chat);
}

// ================================================================ the copy
async function copySuite() {
    console.log("chrome strings and template");
    const keys = ["micStarting", "listening", "micStop", "micCancel", "transcribing", "heardNothing", "hearAsVi",
                  "hearAsEn", "micDenied", "micCannot", "micUnsupported", "noViVoice", "amountOnScreen", "stopReading"];
    const missing = keys.filter((k) => !(CONTENT.chrome[k] && CONTENT.chrome[k].en && CONTENT.chrome[k].vi
                                         && CONTENT.chrome[k].en !== CONTENT.chrome[k].vi));
    check(!missing.length, "every OC3 chrome key exists in English and Vietnamese", missing.join(","));
    check(keys.every((k) => !/odoo/i.test(CONTENT.chrome[k].en + CONTENT.chrome[k].vi)), "no vendor name in them");
    const xml = fs.readFileSync(path.join(ROOT, "pb_payroll_ai_insights", "static", "src", "components",
                                          "ai_insight_chat", "ai_insight_chat.xml"), "utf-8");
    const emb = xml.slice(xml.indexOf('t-name="pb_payroll_ai_insights.AiInsightChatEmbedded"'));
    check(!/\bfa-/.test(emb), "the one chat draws no Font Awesome icon");
    const sprite = fs.readFileSync(path.join(ROOT, "pb_learn", "static", "src", "journey", "icons.xml"), "utf-8");
    const used = [...new Set([...emb.matchAll(/#lrn-i-([a-z0-9-]+)/g)].map((m) => m[1]))];
    check(used.every((id) => sprite.includes(`id="lrn-i-${id}"`)), "every icon the chat uses is in the sprite", used.join(","));
    const js = fs.readFileSync(path.join(ROOT, "pb_payroll_ai_insights", "static", "src", "components",
                                         "ai_insight_chat", "ai_insight_chat.js"), "utf-8");
    check(!/\(\?<[!=]/.test(js), "no look-behind in the chat's regular expressions (older Safari)");
    check(!/rpc_send_message[\s\S]{0,40}_sendForText|_land[\s\S]{0,400}submitComposer\(/.test(js.slice(js.indexOf("_land(heard"), js.indexOf("get hearAsLabel"))),
          "landing the words never sends them");
}

for (const suite of [recorderSuite, readBackSuite, copySuite]) {
    try {
        await suite();
    } catch (e) {
        check(false, `${suite.name} crashed`, String(e && e.stack || e));
    }
}
Date.now = realNow;
summary();
