/**
 * ONECHAT — PayAI's free-text answers drawn as safe light markdown, in node.
 *
 * The answer text becomes a tree of plain strings (`richBlocks`, in
 * pb_payroll_ai_insights ai_insight_chat.js); the RichText templates print
 * every string with t-esc. This file checks
 *   - the whitelist: **bold**, *italic*, ***both***, `code`, numbered and
 *     bulleted lists (one nested level), "#" headings as a bold line, line
 *     breaks and paragraphs; anything else stays as written;
 *   - the tree holds only plain strings, booleans and a list's start number —
 *     no HTML from the model can ever reach the page (img/onerror, a <b>
 *     inside **…**, javascript: links, <script>, an svg onload);
 *   - the templates print with t-esc only (no t-out, no href / src / style /
 *     event attributes) and the three answer places use them, while what the
 *     person typed stays plain text;
 *   - read-aloud speaks the words without the stars, bullets or "#".
 *
 * Run: node pb_payai_actions/tests/js/onechat_rich.test.mjs   (exit 1 on failure)
 */
import fs from "node:fs";
import path from "node:path";
import { check, load, summary, ROOT } from "./harness.mjs";

const CHAT = "@pb_payroll_ai_insights/components/ai_insight_chat/ai_insight_chat";
const chatMod = await load(CHAT);
const fullMod = await load(`${CHAT}_full`, [CHAT]);
const { richBlocks, richInline, speechText, AiInsightChat } = chatMod;
const { AiInsightChatFull } = fullMod;

// ------------------------------------------------------------- helpers
/** What the screen shows: the templates' output, text escaped as t-esc
 *  escapes it (OWL sets text, never HTML). */
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
function htmlLine(line) {
    return line.map((sp) => {
        if (sp.code) { return `<code>${esc(sp.text)}</code>`; }
        if (sp.b && sp.i) { return `<strong><em>${esc(sp.text)}</em></strong>`; }
        if (sp.b) { return `<strong>${esc(sp.text)}</strong>`; }
        if (sp.i) { return `<em>${esc(sp.text)}</em>`; }
        return esc(sp.text);
    }).join("");
}
const htmlLines = (lines) => lines.map(htmlLine).join("<br>");
function htmlList(lst) {
    const tag = lst.kind;
    const start = tag === "ol" ? ` start="${Number(lst.start)}"` : "";
    const items = lst.items.map((it) => `<li>${htmlLines(it.lines)}${(it.subs || []).map(htmlList).join("")}</li>`);
    return `<${tag}${start}>${items.join("")}</${tag}>`;
}
function html(text) {
    return richBlocks(text).map((b) => (b.kind === "p" ? `<p>${htmlLines(b.lines)}</p>` : htmlList(b))).join("");
}
const plain = (text) => ({ text, b: false, i: false, code: false });
const bold = (text) => ({ text, b: true, i: false, code: false });
const ital = (text) => ({ text, b: false, i: true, code: false });
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

/** Every node is one of the known shapes and holds only plain values. */
function treeIsInert(blocks) {
    const spanOk = (sp) => sp && Object.keys(sp).sort().join(",") === "b,code,i,text"
        && typeof sp.text === "string" && [sp.b, sp.i, sp.code].every((v) => typeof v === "boolean");
    const linesOk = (lines) => Array.isArray(lines) && lines.every((l) => Array.isArray(l) && l.every(spanOk));
    const listOk = (l, nested) => ["ol", "ul"].includes(l.kind) && Number.isInteger(l.start)
        && Array.isArray(l.items) && l.items.every((it) => linesOk(it.lines)
            && (nested ? !it.subs : Array.isArray(it.subs) && it.subs.every((s) => listOk(s, true))));
    return Array.isArray(blocks) && blocks.every((b) => (b.kind === "p" ? linesOk(b.lines) : listOk(b, false)));
}

// ------------------------------------------------------------ whitelist
console.log("the whitelist");
{
    const t = richBlocks("**Home › Approvals**");
    check(t.length === 1 && t[0].kind === "p" && same(t[0].lines, [[bold("Home › Approvals")]]),
          "**Home › Approvals** is one bold piece, the stars gone", JSON.stringify(t));
    check(html("Open **Home › Approvals** now.") === "<p>Open <strong>Home › Approvals</strong> now.</p>",
          "… inside a sentence", html("Open **Home › Approvals** now."));
}
{
    const t = richBlocks("1. **Dữ liệu lương**: kiểm tra\n2. **Phê duyệt**: bấm Duyệt");
    check(t.length === 1 && t[0].kind === "ol" && t[0].start === 1 && t[0].items.length === 2,
          "a numbered answer is one numbered list", JSON.stringify(t));
    check(same(t[0].items[0].lines, [[bold("Dữ liệu lương"), plain(": kiểm tra")]]),
          "1. **Dữ liệu lương**: → bold label, then the words", JSON.stringify(t[0].items[0].lines));
}
check(html("3) Third\n4) Fourth") === '<ol start="3"><li>Third</li><li>Fourth</li></ol>',
      "a list keeps its own first number (3) …)", html("3) Third\n4) Fourth"));
check(html("Steps:\n1. Open\n\nThen:\n2. Run") === '<p>Steps:</p><ol start="1"><li>Open</li></ol><p>Then:</p><ol start="2"><li>Run</li></ol>',
      "a list broken by a paragraph carries on from its number", html("Steps:\n1. Open\n\nThen:\n2. Run"));
check(html("- one\n- two") === "<ul><li>one</li><li>two</li></ul>", "- bullets", html("- one\n- two"));
check(html("* one\n+ two\n• three") === "<ul><li>one</li><li>two</li><li>three</li></ul>",
      "* + • bullets", html("* one\n+ two\n• three"));
check(html("1. Pay data\n   - check hours\n   - check leave\n2. Approve")
          === '<ol start="1"><li>Pay data<ul><li>check hours</li><li>check leave</li></ul></li><li>Approve</li></ol>',
      "an indented list sits inside its item", html("1. Pay data\n   - check hours\n   - check leave\n2. Approve"));
check(html("- Open the run\n  then press Run") === "<ul><li>Open the run<br>then press Run</li></ul>",
      "an indented line continues the item", html("- Open the run\n  then press Run"));
check(html("Line one\nLine two\n\nPara two") === "<p>Line one<br>Line two</p><p>Para two</p>",
      "line breaks and paragraphs", html("Line one\nLine two\n\nPara two"));
check(html("Line one\r\nLine two") === "<p>Line one<br>Line two</p>", "Windows line ends");
check(html("### Next steps\nOpen it.") === "<p><strong>Next steps</strong></p><p>Open it.</p>",
      "a # heading is a bold line", html("### Next steps\nOpen it."));
check(html("Before\n---\nAfter") === "<p>Before</p><p>After</p>", "--- separates paragraphs", html("Before\n---\nAfter"));
check(same(richInline("a *note* b"), [plain("a "), ital("note"), plain(" b")]), "*italic*");
check(same(richInline("***both***"), [{ text: "both", b: true, i: true, code: false }]), "***bold italic***");
check(html("**Run *now* please**") === "<p><strong>Run </strong><strong><em>now</em></strong><strong> please</strong></p>",
      "italic inside bold", html("**Run *now* please**"));
check(html("Use `pay_role` here") === "<p>Use <code>pay_role</code> here</p>", "`code`", html("Use `pay_role` here"));
check(html("`**not bold**`") === "<p><code>**not bold**</code></p>", "stars inside code stay as written");
for (const [said, shown] of [
    ["5 * 3 * 2", "<p>5 * 3 * 2</p>"],
    ["Rate*Hours*1.5", "<p>Rate*Hours*1.5</p>"],
    ["** alone", "<p>** alone</p>"],
    ["**unclosed bold", "<p>**unclosed bold</p>"],
    ["a ** b ** c", "<p>a ** b ** c</p>"],
    ["-950 is the change", "<p>-950 is the change</p>"],
    ["2026. A good year", "<p>2026. A good year</p>"],
    ["__init__ and snake_case", "<p>__init__ and snake_case</p>"],
]) {
    check(html(said) === shown, `stays as written: "${said}"`, html(said));
}
check(same(richBlocks(""), []) && same(richBlocks(null), []) && same(richBlocks(undefined), []),
      "nothing → nothing");
check(richBlocks("**x** y") === richBlocks("**x** y"), "the same answer is parsed once (cached)");

// ------------------------------------------------------------- XSS
console.log("nothing from the model becomes HTML");
const ATTACKS = [
    "<img src=x onerror=alert(1)>",
    "**<b>x</b>**",
    "[click me](javascript:alert(1))",
    "javascript:alert(1)",
    "<script>alert(document.cookie)</script>",
    "1. \"><svg onload=alert(1)>\n2. <iframe src=//evil>",
    "`<img src=x onerror=alert(1)>`",
    "*<a href=\"javascript:alert(1)\">x</a>*",
    "![x](https://evil.example/x.png)",
    "<p onclick=alert(1)>**hi**</p>",
    "&lt;img src=x&gt; and &#60;b&#62;",
    "### <style>body{display:none}</style>",
];
for (const attack of ATTACKS) {
    const tree = richBlocks(attack);
    const out = html(attack);
    check(treeIsInert(tree), `the tree is plain strings only: ${JSON.stringify(attack)}`, JSON.stringify(tree));
    // Escaped text holds no "<" or ">", so every tag left is one the
    // templates draw: p, br, strong, em, code, ol (start only), ul, li.
    const tags = out.match(/<[^>]*>/g) || [];
    const bad = tags.filter((tg) => !/^<\/?(?:p|br|strong|em|code|ul|li)>$|^<ol start="\d+">$|^<\/ol>$/.test(tg));
    check(!bad.length, `… the screen gets no tag, link, image, script or handler: ${JSON.stringify(attack)}`,
          bad.join(" "));
}
check(same(richBlocks("<img src=x onerror=alert(1)>")[0].lines, [[plain("<img src=x onerror=alert(1)>")]]),
      "<img src=x onerror=alert(1)> is shown as those characters");
check(html("**<b>x</b>**") === "<p><strong>&lt;b&gt;x&lt;/b&gt;</strong></p>", "**<b>x</b>** → bold text \"<b>x</b>\"",
      html("**<b>x</b>**"));
check(html("[click me](javascript:alert(1))") === "<p>[click me](javascript:alert(1))</p>",
      "a markdown link stays text — no link is ever made");
check(html("&lt;b&gt;") === "<p>&amp;lt;b&amp;gt;</p>", "entities are not decoded into tags");

// ------------------------------------------------------- the templates
console.log("the templates");
const DIR = path.join(ROOT, "pb_payroll_ai_insights", "static", "src", "components", "ai_insight_chat");
const xml = fs.readFileSync(path.join(DIR, "ai_insight_chat.xml"), "utf-8");
const fullXml = fs.readFileSync(path.join(DIR, "ai_insight_chat_full.xml"), "utf-8");
const tpl = (name) => {
    const at = xml.indexOf(`t-name="${name}"`);
    if (at < 0) { return ""; }
    const next = xml.indexOf("t-name=", at + 10);
    return xml.slice(at, next < 0 ? xml.length : next);
};
const RICH = ["RichLine", "RichLines", "RichList", "RichSubList", "RichText"].map((n) => `pb_payroll_ai_insights.${n}`);
check(RICH.every((n) => tpl(n)), "the five RichText templates exist", RICH.filter((n) => !tpl(n)).join(","));
const richSrc = RICH.map(tpl).join("\n");
check(!/t-out|t-raw|t-att-href|t-att-src|t-att-style|t-attf-|t-on-|innerHTML|markup/.test(richSrc),
      "they print with t-esc only: no t-out, no href / src / style, no handler");
check((richSrc.match(/t-esc="sp\.text"/g) || []).length === 5, "every piece of text goes through t-esc");
check(/t-att-start="lst\.start"/.test(richSrc) && /t-att-start="sub\.start"/.test(richSrc),
      "the only attribute taken from the tree is a list's start number");
const place = (src, cls) => {
    const m = new RegExp(`<div class="${cls}"[^>]*>[\\s\\S]*?</div>`).exec(src);
    return m ? m[0] : "";
};
for (const [src, cls] of [[xml, "payai-msg-text"], [xml, "payai-embed-text"], [fullXml, "payai-full-msg-text"]]) {
    const div = place(src, cls);
    check(/richOf\(msg\.content\)/.test(div) && /t-call="pb_payroll_ai_insights\.RichText"/.test(div),
          `${cls}: a PayAI answer is drawn through RichText`, div);
    check(/t-if="msg\.role === 'user'" t-esc="msg\.content"/.test(div) && !/t-out/.test(div),
          `${cls}: what the person typed stays plain text`);
}
check(!/t-esc="msg\.content"\/>/.test(place(xml, "payai-embed-text").replace(/t-if="msg\.role === 'user'" t-esc="msg\.content"\/>/, "")),
      "the one chat no longer prints the raw answer with its stars");
const cards = fs.readFileSync(path.join(ROOT, "pb_payai_actions", "static", "src", "xml", "cards.xml"), "utf-8");
check(/hasclass\('payai-embed-text'\)/.test(cards) && /<div class="payai-embed-text"/.test(xml)
      && /<div class="payai-msg-text"/.test(xml),
      "the plan card's hooks on payai-embed-text / payai-msg-text still find their div");
check(typeof AiInsightChat.prototype.richOf === "function" && typeof AiInsightChatFull.prototype.richOf === "function",
      "the pill / one chat and the full-page chat both offer richOf");
check(AiInsightChat.prototype.richOf.call({}, "**a**") === richBlocks("**a**"), "richOf is richBlocks");
const js = fs.readFileSync(path.join(DIR, "ai_insight_chat.js"), "utf-8");
const parser = js.slice(js.indexOf("const RICH_OL"), js.indexOf("export class AiInsightChat"));
check(parser.length > 500 && !/innerHTML|markup\(|insertAdjacentHTML|document\./.test(parser),
      "the parser builds no HTML and touches no page");
check(!/\(\?<[!=]/.test(parser), "no look-behind in the parser (older Safari)");
const scss = fs.readFileSync(path.join(DIR, "ai_insight_chat.scss"), "utf-8");
check(/\.payai-embed-text\.payai-rich/.test(scss) && /white-space: normal/.test(scss),
      "a drawn answer drops pre-wrap (its line breaks are real)");
check(!/gradient/.test(scss.slice(scss.indexOf(".payai-msg-text.payai-rich"))), "no gradient in the new styles");

// ------------------------------------------------------- read aloud
console.log("read aloud");
const W = "an amount shown on screen";
for (const [said, heard] of [
    ["**Home › Approvals**", "Home › Approvals"],
    ["1. **Dữ liệu lương**: kiểm tra\n2. **Phê duyệt**: bấm Duyệt", "1. Dữ liệu lương: kiểm tra 2. Phê duyệt: bấm Duyệt"],
    ["- **Open** the run\n- press *Run*", "Open the run press Run"],
    ["### Next steps\n---\nUse `Pay Run`.", "Next steps Use Pay Run."],
    ["• Check hours\n+ Check leave", "Check hours Check leave"],
    ["Net pay is **12,000,000**.", `Net pay is ${W}.`],
    ["- **USD 950** for Lan", `${W} for Lan`],
]) {
    const out = speechText(said);
    check(out === heard, `read aloud: ${JSON.stringify(said)} → "${heard}"`, out);
    check(!/[*#`•]/.test(out), `… no stars, "#", backticks or bullets spoken: ${JSON.stringify(said)}`);
}
check(speechText("<img src=x onerror=alert(1)> Open **Pay Run**") === "Open Pay Run",
      "markup is never read out", speechText("<img src=x onerror=alert(1)> Open **Pay Run**"));

summary();
