/**
 * PAYAI FIX-1, cluster E — the client halves, run in node (no browser).
 *
 *   P4:link-1 / test-1  the Home hub hands its deep link to the Approvals lens
 *                       (HubShell → lensProps.arrival → PbInbox), once;
 *   P4:link-3           the drawer opens on the tab that lists the request;
 *   P4:link-4           a gone / unreadable request is a notice, not a drawer;
 *   P4:vi-13 / test-2   the card folds the typed word exactly as the server
 *                       (shared table word_fold_cases.json), and a door
 *                       forwards `focus` into the action context;
 *   P3:crit-6           each Remind chip works on its own; a dropped answer
 *                       gives the chip back;
 *   P3:crit-7           a typed decision with no reply never says
 *                       "Nothing was done"; one the server answered with
 *                       an error does (rolled back), with its reason.
 *
 * Run: node pb_payai_actions/tests/js/client_fix.test.mjs   (exit 1 on failure)
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { check, load, mount, summary } from "./harness.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const pb = globalThis.__pb;
const TABLE = JSON.parse(fs.readFileSync(path.join(HERE, "word_fold_cases.json"), "utf-8"));

// ------------------------------------------------------------- services
let ormLog = [];
let ormAnswer = () => null;
let notes = [];
let doActions = [];
function resetServices() {
    ormLog = [];
    notes = [];
    doActions = [];
    pb.services.orm = {
        call: async (model, method, args = []) => {
            ormLog.push({ model, method, args });
            return ormAnswer(method, args);
        },
    };
    pb.services.notification = { add: (text, opts) => notes.push({ text: String(text), opts }) };
    pb.services.action = {
        doAction: async (target, opts) => { doActions.push({ target, opts }); },
        // What Odoo 19's getter really returns: a Promise, never an action.
        get currentAction() { return Promise.resolve({ context: { pb_focus: "request:42" } }); },
    };
}

/** The inbox's default answers: the pile, and an empty list. */
function inboxAnswers(where) {
    return (method, args) => {
        if (method === "locate_request") {
            if (typeof where === "function") { return where(args); }
            return where;
        }
        if (method === "list_requests") {
            return { cards: [], counts: {}, areas: [], money: [], tab: args[0], scope: args[3] };
        }
        return null;
    };
}

const calls = (method) => ormLog.filter((c) => c.method === method);
const argsOf = (method, i = 0) => (calls(method)[i] || {}).args || [];

// =================================================== link-1 / link-3 / link-4
async function arrivalSuite() {
    console.log("Home hub → Approvals lens deep link (P4:link-1, link-3, link-4, test-1)");
    const { PbHomeHub } = await load("@pb_home_hub/js/home_hub", [
        "@pb_hub/js/hub_shell", "@pb_hub/js/hub_nav", "@pb_approval_config/js/inbox"]);
    const { HubShell } = await load("@pb_hub/js/hub_shell", ["@pb_hub/js/hub_nav"]);
    const inboxMod = await load("@pb_approval_config/js/inbox");
    const { PbInbox, focusRequest } = inboxMod;

    // focusRequest: the one format, both carriers.
    check(JSON.stringify(focusRequest({ pb_focus: "request:42" })) === '{"id":42,"scope":"me"}',
          "focusRequest reads an action context");
    check(JSON.stringify(focusRequest({ lens: "approvals", focus: "request:42:org" }))
          === '{"id":42,"scope":"org"}', "focusRequest reads the hub arrival payload");
    check(focusRequest({ pb_focus: "month:2026-06" }) === null
          && focusRequest({ focus: "queue" }) === null && focusRequest(null) === null,
          "focusRequest leaves other screens' words alone");

    // The hub, opened the way PayAI's door opens it (openHub → doAction).
    const openWith = async (focus) => {
        resetServices();
        ormAnswer = () => null;
        const action = { tag: "pb_home_hub",
                         context: { pb_lens: "approvals", pb_focus: focus } };
        const home = await mount(PbHomeHub, { action });
        const shell = await mount(HubShell, { config: home.config, action }, {},
                                  { start: false });
        return { home, shell };
    };

    const { home, shell } = await openWith("request:42");
    const def = home.config.lenses.find((l) => l.key === "approvals");
    check(def && def.wantsArrival === true, "the Approvals lens asks for the hub's arrival");
    check(shell.state.lens === "approvals", "the hub raises the Approvals lens");
    const props = shell.lensProps;
    check(props.arrival && props.arrival.focus === "request:42",
          "the lens is mounted WITH the deep link", JSON.stringify(props));

    // A request that is waiting for someone else's step → "All I can see".
    ormAnswer = inboxAnswers({ id: 42, tab: "all", scope: "me" });
    const inbox = await mount(PbInbox, props);
    check(calls("locate_request").length === 1
          && JSON.stringify(argsOf("locate_request")) === "[42,\"me\"]",
          "the inbox asks the server where request 42 lives",
          JSON.stringify(ormLog.map((c) => c.method)));
    check(inbox.state.openId === 42, "the drawer opens on request 42",
          `openId=${inbox.state.openId}`);
    check(inbox.state.tab === "all" && calls("list_requests").length === 1
          && argsOf("list_requests")[0] === "all",
          "the list is read once, on the tab that lists it");

    // Tab away and back: the same arrival never pops the drawer again.
    shell.state.lens = "pulse";
    void shell.lensProps;
    shell.state.lens = "approvals";
    const again = shell.lensProps;
    check(again.arrival === props.arrival, "the arrival keeps its identity across lens switches");
    ormLog = [];
    const back = await mount(PbInbox, again);
    check(back.state.openId === 0 && calls("locate_request").length === 0
          && back.state.tab === "mine",
          "coming back to the lens does not reopen the request");

    // link-3: a decided request opens on "Finished", where it is listed.
    {
        const { shell: s2 } = await openWith("request:50");
        ormAnswer = inboxAnswers({ id: 50, tab: "done", scope: "me" });
        const ib = await mount(PbInbox, s2.lensProps);
        check(ib.state.tab === "done" && ib.state.openId === 50
              && argsOf("list_requests")[0] === "done",
              "an approved request opens on Finished (link-3)",
              `tab=${ib.state.tab} openId=${ib.state.openId}`);
    }
    // ... and one waiting for me on "My turn"; a wider scope is kept.
    {
        const { shell: s3 } = await openWith("request:51:org");
        ormAnswer = inboxAnswers({ id: 51, tab: "mine", scope: "org" });
        const ib = await mount(PbInbox, s3.lensProps);
        check(JSON.stringify(argsOf("locate_request")) === "[51,\"org\"]"
              && ib.state.scope === "org" && ib.state.tab === "mine"
              && argsOf("list_requests")[3] === "org",
              "the scope in the link is asked for and kept");
    }
    // link-4: gone or not readable → a plain notice, no drawer, the usual list.
    {
        const { shell: s4 } = await openWith("request:99");
        ormAnswer = (method, args) => {
            if (method === "locate_request") {
                const err = new Error("rpc");
                err.data = { message: "That request no longer exists." };
                throw err;
            }
            return inboxAnswers(null)(method, args);
        };
        const ib = await mount(PbInbox, s4.lensProps);
        check(ib.state.openId === 0 && ib.state.tab === "mine" && ib.state.scope === "me",
              "a gone request opens no drawer (link-4)");
        check(notes.length === 1 && notes[0].text === "That request no longer exists.",
              "… and says so in the server's plain words", JSON.stringify(notes));
    }
    {
        const { shell: s5 } = await openWith("request:60");
        ormAnswer = inboxAnswers({ id: 60, tab: false, scope: "me" });
        const ib = await mount(PbInbox, s5.lensProps);
        check(ib.state.openId === 0 && notes.length === 1,
              "a request no pile lists opens no drawer");
    }
    // The standalone client action still reads its own context.
    {
        resetServices();
        ormAnswer = inboxAnswers({ id: 44, tab: "returned", scope: "me" });
        const ib = await mount(PbInbox, { action: { context: { pb_focus: "request:44" } } });
        check(ib.state.openId === 44 && ib.state.tab === "returned",
              "the standalone Approvals action opens its focused request");
    }
    // No link at all: nothing is asked, "My turn" as always.
    {
        resetServices();
        ormAnswer = inboxAnswers(null);
        const ib = await mount(PbInbox, { embedded: true });
        check(calls("locate_request").length === 0 && ib.state.openId === 0,
              "a plain visit is untouched");
    }
}

// ====================================================== chat_patch halves
async function chatSuite() {
    console.log("PayAI card client halves (P4:vi-13, test-2, P3:crit-6, crit-7)");
    const chat = await load("@pb_payai_actions/js/chat_patch", ["@pb_hub/js/hub_nav"]);
    const { normWord, wordMatches } = chat;

    // ---- vi-13: one fold, both sides (the server half runs the same table).
    for (const row of TABLE.fold) {
        const got = normWord(row.in);
        check(got === row.out, `fold ${JSON.stringify(row.in)} → ${JSON.stringify(row.out)}`,
              `card gave ${JSON.stringify(got)}`);
    }
    for (const row of TABLE.match) {
        const got = wordMatches(row.typed, { word: row.words[0], words: row.words });
        check(got === row.ok, `typed ${JSON.stringify(row.typed)} vs ${row.words.join("/")} → ${row.ok}`);
    }

    const patchObj = pb.patches.map((p) => p.obj).find((o) => typeof o._payaiRunDoor === "function");
    check(Boolean(patchObj), "the chat patch is registered");
    if (!patchObj) { return; }

    // ---- test-2: a door forwards focus + context into the action.
    {
        resetServices();
        const self = Object.create(patchObj);
        self.actionService = pb.services.action;
        self.notification = pb.services.notification;
        self.closePanel = () => {};
        self.env = { services: {} };
        self._payaiRunDoor({ id: "door", hub: { tag: "pb_home_hub", lens: "approvals",
            focus: "request:42", context: { pb_focus: "request:42" } } });
        await new Promise((r) => setTimeout(r, 0));
        const call = doActions[0] || {};
        const ctx = (call.opts && call.opts.additionalContext) || {};
        check(call.target === "pb_home_hub" && ctx.pb_lens === "approvals"
              && ctx.pb_focus === "request:42",
              "the door opens Home on Approvals with pb_focus", JSON.stringify(call));
    }

    // ---- crit-6: Remind chips one by one.
    const chatSelf = (answerWithCard) => {
        const self = Object.create(patchObj);
        self.state = { isLoading: false, messages: [] };
        self.sent = [];
        self.sendSuggestion = async (text) => {
            self.sent.push({ text, resolve: self._payaiResolve });
            self._payaiResolve = null;
            self.state.messages.push({ role: "user", content: text });
            self.state.messages.push(answerWithCard()
                ? { role: "assistant", card: { task_id: 7, transient: true, title: "Reminded" } }
                : { role: "assistant", content: "That did not work." });
        };
        // the shipped P3 card had no per-chip helpers: judge it by what its
        // template read (one `picked` for the whole card)
        if (typeof self.payaiChipOff !== "function") {
            self.payaiChipOff = (card) => Boolean(card.picked);
            self.payaiChipOn = (card, chip) => card.picked === chip.value;
        }
        return self;
    };
    {
        const self = chatSelf(() => true);
        const chips = [{ label: "Remind Minh", value: "5:11" }, { label: "Remind Lan", value: "5:12" }];
        const msg = { card: { task_id: 7, chip_action: "remind", chip_slot: "item", chips } };
        await self.payaiPick(msg, chips[0]);
        check(self.payaiChipOff(msg.card, chips[0]) && !self.payaiChipOff(msg.card, chips[1]),
              "after Remind Minh, only Minh's chip is used up");
        check(self.payaiChipOn(msg.card, chips[0]) && !self.payaiChipOn(msg.card, chips[1]),
              "… and only Minh's chip is drawn as chosen");
        await self.payaiPick(msg, chips[1]);
        check(self.sent.length === 2 && self.sent[1].resolve.value === "5:12"
              && self.sent[1].resolve.action === "remind",
              "Remind Lan is sent too (crit-6)", JSON.stringify(self.sent));
        await self.payaiPick(msg, chips[1]);
        check(self.sent.length === 2, "a used Remind chip is not sent twice");
    }
    {
        let ok = false;
        const self = chatSelf(() => ok);
        const chips = [{ label: "Remind Minh", value: "5:11" }];
        const msg = { card: { task_id: 7, chip_action: "remind", chip_slot: "item", chips } };
        await self.payaiPick(msg, chips[0]);
        check(!self.payaiChipOff(msg.card, chips[0]),
              "a Remind that got no answer gives the chip back");
        ok = true;
        await self.payaiPick(msg, chips[0]);
        check(self.sent.length === 2 && self.payaiChipOff(msg.card, chips[0]),
              "… and it can be pressed again");
    }
    {
        // the chat was busy and sent nothing: the chip comes back and its
        // answer does not ride along with the next thing typed
        const self = chatSelf(() => true);
        self.sendSuggestion = async () => {};
        const chips = [{ label: "Remind Minh", value: "5:11" }];
        const msg = { card: { task_id: 7, chip_action: "remind", chip_slot: "item", chips } };
        await self.payaiPick(msg, chips[0]);
        check(!self.payaiChipOff(msg.card, chips[0]) && !self._payaiResolve,
              "a chip the busy chat did not send leaves no answer behind");
    }
    {
        const self = chatSelf(() => true);
        const chips = [{ label: "June", value: "1" }, { label: "July", value: "2" }];
        const msg = { card: { task_id: 8, chip_slot: "run", chips } };
        await self.payaiPick(msg, chips[0]);
        check(self.payaiChipOff(msg.card, chips[1]) && self.payaiChipOn(msg.card, chips[0]),
              "an ordinary choice still closes every chip of its card");
        await self.payaiPick(msg, chips[1]);
        check(self.sent.length === 1, "… and a second choice is not sent");
    }
    {
        const self = chatSelf(() => false);
        const chips = [{ label: "June", value: "1" }];
        const msg = { card: { task_id: 8, chip_slot: "run", chips } };
        await self.payaiPick(msg, chips[0]);
        check(!self.payaiChipOff(msg.card, chips[0]),
              "an ordinary choice that got no answer is pressable again");
    }

    // ---- crit-7: the typed decision whose reply was lost.
    // What Odoo 19's rpc really throws: a ConnectionLostError (a plain Error
    // subclass) when no answer came, an RPCError (name "RPC_ERROR", type
    // "server") when the server answered with an exception.
    const serverError = (exceptionName, message) => {
        const err = new Error(message || "Odoo Server Error");
        err.name = "RPC_ERROR";
        err.type = "server";
        err.exceptionName = exceptionName;
        err.data = { name: exceptionName, message: message || "", debug: "Traceback ..." };
        return err;
    };
    const lostReply = async (card, method, extra, thrown = () => new Error("offline")) => {
        resetServices();
        const self = Object.create(patchObj);
        self.notification = pb.services.notification;
        self._payaiRpc = async () => { throw thrown(); };
        const msg = { card: { ...card, busy: true } };
        await self._payaiTaskCall(msg, method, extra);
        return { msg, text: (notes[0] || {}).text || "" };
    };
    {
        const { msg, text } = await lostReply({ task_id: 9, tier: "decide", state: "planned" },
                                              "rpc_confirm_task", ["typed", "APPROVE", ""]);
        check(!/Nothing was done/.test(text) && /could not hear back/.test(text),
              "a typed decision with no reply does not claim nothing was done (crit-7)", text);
        check(msg.card.busy === false, "… and the button can be pressed again to see what happened");
    }
    {
        const { text } = await lostReply({ task_id: 10, tier: "prepare", state: "planned" },
                                         "rpc_confirm_task", ["tap"]);
        check(/Nothing was done/.test(text), "other calls keep their own words");
    }
    {
        // the server answered with a refusal: rolled back, so nothing was
        // done — say so with its reason, not "could not hear back"
        const { msg, text } = await lostReply({ task_id: 11, tier: "decide", state: "planned" },
            "rpc_confirm_task", ["typed", "APPROVE", ""],
            () => serverError("odoo.exceptions.AccessError",
                              "You are not allowed to decide this request."));
        check(!/could not hear back/.test(text) && /Nothing was done/.test(text)
              && /You are not allowed to decide this request\./.test(text),
              "a decision the server refused says nothing was done, with its reason", text);
        check(msg.card.busy === false, "… and the button is given back");
    }
    {
        // an engine fault (not a message for people): the plain wording,
        // never the raw technical text
        const { text } = await lostReply({ task_id: 12, tier: "decide", state: "planned" },
            "rpc_confirm_task", ["typed", "APPROVE", ""],
            () => serverError("builtins.KeyError", "'line_ids'"));
        check(!/could not hear back/.test(text) && /Nothing was done/.test(text)
              && !/line_ids/.test(text),
              "an engine fault on a decision says nothing was done, without the raw text", text);
    }
    {
        // a real lost connection on a decision keeps the careful wording
        const { text } = await lostReply({ task_id: 13, tier: "decide", state: "planned" },
            "rpc_confirm_task", ["typed", "APPROVE", ""], () => {
                const err = new Error('Connection to "/web/dataset/call_kw" couldn\'t be established');
                err.url = "/web/dataset/call_kw";
                return err;
            });
        check(/could not hear back/.test(text), "a lost connection on a decision stays careful", text);
    }
    {
        const { text } = await lostReply({ task_id: 14, tier: "prepare", state: "planned" },
            "rpc_task_undo", [],
            () => serverError("odoo.exceptions.UserError", "The ten minutes are up."));
        check(text === "Nothing was done. The ten minutes are up.",
              "an undo the server refused gives its reason", text);
    }
}

for (const suite of [arrivalSuite, chatSuite]) {
    try {
        await suite();
    } catch (e) {
        check(false, `${suite.name} crashed`, String(e && e.stack || e));
    }
}
summary();
