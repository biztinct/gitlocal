// VIFIX P1 scope C: live Vietnamese sweep of every sidebar entry and hub tab (clone only).
//
// Run (Node >= 22; a headless Chrome already listening on --port; the clone reachable at --base):
//   node vifix_live_sweep.mjs --port 9577 --base http://127.0.0.1:18077 --db vifixp1clone \
//        --login qa.test@payobook.com --secret-file <memory file holding  password `...`> \
//        --out <dir>
// The password is read from --secret-file at runtime and never printed or written anywhere.
// Writes <out>/sweep.json (one record per screen: path, strings, attrs, screenshot) and
// <out>/shots/*.png. Classify with vifix_live_report.py.
//
// How a screen is reached: through the menu, the way a user does (LEARNREV LR80): click the
// sidebar entry (`.pb-nav-item`, expanding sections and sub-entries first), then click each hub
// tab (`.pbhub-rail__b`). Detail drawers: on the screens named in DETAILS the first row/card is
// opened, collected, then closed with Escape / browser back.
import fs from "node:fs";
import path from "node:path";
import { openPage, sleep } from "./vifix_cdp.mjs";

const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, all) => {
    if (v.startsWith("--")) a.push([v.slice(2), all[i + 1]]);
    return a;
}, []));
const BASE = args.base || "http://127.0.0.1:18077";
const OUT = args.out;
const ONLY = args.only ? new RegExp(args.only, "i") : null;
fs.mkdirSync(path.join(OUT, "shots"), { recursive: true });

// Visible-text collector: text nodes and the user-facing attributes, with a little context.
const COLLECT = `(() => {
  const vis = (el) => {
    if (!el || !el.getClientRects().length) return false;
    const cs = getComputedStyle(el);
    return cs.visibility !== 'hidden' && cs.display !== 'none' && parseFloat(cs.opacity || '1') > 0.05;
  };
  const ctx = (el) => {
    const parts = [];
    for (let e = el, i = 0; e && e !== document.body && i < 4; e = e.parentElement, i++) {
      const c = (e.className && e.className.toString().split(/\\s+/).filter(Boolean)[0]) || '';
      parts.push(e.tagName.toLowerCase() + (c ? '.' + c : ''));
    }
    return parts.join('<');
  };
  const isData = (el) => !!el.closest('td.o_data_cell, .o_field_widget, .o_kanban_record .o_text_overflow, [contenteditable], .o_mail_body, .o-mail-Message-body, input, textarea, select, .pbx-data, [data-pb-data]');
  const texts = new Map();
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) {
    const t = n.nodeValue.replace(/\\s+/g, ' ').trim();
    if (!t || !/[A-Za-z]/.test(t)) continue;
    const el = n.parentElement;
    if (!el || ['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE'].includes(el.tagName) || !vis(el)) continue;
    if (!texts.has(t)) texts.set(t, { t, ctx: ctx(el), data: isData(el) });
  }
  const attrs = new Map();
  for (const el of document.querySelectorAll('[placeholder],[title],[aria-label],[data-tooltip]')) {
    if (!vis(el)) continue;
    for (const a of ['placeholder', 'title', 'aria-label', 'data-tooltip']) {
      const v = (el.getAttribute(a) || '').replace(/\\s+/g, ' ').trim();
      if (v && /[A-Za-z]/.test(v) && !attrs.has(a + '|' + v)) attrs.set(a + '|' + v, { a, t: v, ctx: ctx(el) });
    }
  }
  return { texts: [...texts.values()], attrs: [...attrs.values()] };
})()`;

const SETTLE = `(() => {
  const busy = document.querySelector('.o_loading_indicator, .o_blockUI, .pbim-skel, .o-skeleton, .placeholder-glow, .o_view_nocontent_loading');
  return !busy;
})()`;

async function settle(page, ms = 2200) {
    await sleep(600);
    await page.waitFor(SETTLE, 12000);
    let last = -1;
    for (let i = 0; i < 8; i++) {
        const len = await page.eval("document.body.innerText.length").catch(() => 0);
        if (len === last) break;
        last = len;
        await sleep(ms / 4);
    }
}

async function dismissOverlays(page) {
    await page.eval(`(() => {
      document.querySelectorAll('.o_notification_close, .o_notification .btn-close, .pbtour-skip, .pb-nudge__close, [aria-label="Đóng"].pbx-close').forEach(b => { try { b.click(); } catch (e) {} });
    })()`).catch(() => {});
}

const records = [];
let shotNo = 0;
async function record(page, screenPath, kind, extra = {}) {
    await dismissOverlays(page);
    const data = await page.eval(COLLECT).catch((e) => ({ texts: [], attrs: [], error: String(e) }));
    const name = String(++shotNo).padStart(3, "0") + "_" + screenPath.replace(/[^\p{L}\p{N}]+/gu, "_").slice(0, 60) + ".png";
    await page.shot(path.join(OUT, "shots", name)).catch(() => {});
    const url = await page.eval("location.pathname + location.search + location.hash").catch(() => "");
    const errs = page.consoleErrors.splice(0);
    records.push({ path: screenPath, kind, url, shot: name, ...data, console: errs.slice(0, 5), ...extra });
    console.log(`${kind.padEnd(7)} ${screenPath}  texts=${data.texts.length} attrs=${data.attrs.length}${errs.length ? " console=" + errs.length : ""}`);
}

// --------------------------------------------------------------------------- sidebar
async function expandSidebar(page) {
    for (let i = 0; i < 3; i++) {
        await page.eval(`(() => {
          document.querySelectorAll('.pb-sidebar .pb-sec-toggle:not(.pb-sec-locked)').forEach(b => {
            const next = b.nextElementSibling;   // an open section renders its .pb-nav-group right after
            if (!next || !next.matches('.pb-nav-group')) b.click();
          });
        })()`).catch(() => {});
        await sleep(300);
    }
}

async function sidebarEntries(page) {
    return page.eval(`(() => {
      const out = [];
      let section = '';
      for (const el of document.querySelectorAll('.pb-sidebar-nav *')) {
        if (el.matches('.pb-nav-group')) continue;
        if (el.matches('.pb-sec-toggle')) { section = (el.querySelector('.pb-sec-name') || el).textContent.replace('›','').trim(); if (el.matches('.pb-sec-locked')) out.push({ title: section, sectionLocked: true, section }); }
        if (el.matches('.pb-nav-item')) out.push({ title: el.getAttribute('title'), sub: el.matches('.pb-subitem'), section, caret: !!el.querySelector('.pb-nav-caret'), locked: el.matches('.pb-locked') });
      }
      return out;
    })()`);
}

async function clickSidebar(page, title, sub) {
    return page.eval(`(() => {
      const b = [...document.querySelectorAll('.pb-sidebar .pb-nav-item' + (${sub} ? '.pb-subitem' : ':not(.pb-subitem)'))].find(x => x.getAttribute('title') === ${JSON.stringify(title)});
      if (!b) return false; b.click(); return true;
    })()`);
}

// Tab rails: the hub shell (.pbhub-rail__b), the Workforce mission shell (.pbms-rail__b) and the
// Settings navigation (.pbst-nav__b). The label is the button's own text as written (textContent;
// the screen shows it in capitals through CSS), not its tooltip.
const TAB_SEL = ".pbhub-rail__b, .pbms-rail__b, .pbst-nav__b";
async function hubTabs(page) {
    return page.eval(`[...document.querySelectorAll(${JSON.stringify(TAB_SEL)})].filter(b => b.getClientRects().length).map(b => (b.textContent || b.getAttribute('aria-label') || b.title || '').replace(/\\s+/g,' ').trim())`).catch(() => []);
}

async function clickHubTab(page, i) {
    return page.eval(`(() => { const b = [...document.querySelectorAll(${JSON.stringify(TAB_SEL)})].filter(b => b.getClientRects().length)[${i}]; if (!b) return false; b.click(); return true; })()`);
}

// Detail drawers / forms: first row or card on the current screen.
const ROW_SELECTORS = [
    ".o_data_row td.o_data_cell", ".o_kanban_record:not(.o_kanban_ghost)",
    "[class*=row][role=button]", "[class*=card][role=button]", "tr[data-id] td", "[data-row-id]",
    ".pbim-row", ".pbx-row", ".pb-row", "[class$=__row]", "[class*=-row ]",
    "tbody tr td",
];
async function openFirstRow(page) {
    return page.eval(`(() => {
      for (const sel of ${JSON.stringify(ROW_SELECTORS)}) {
        const el = [...document.querySelectorAll('.o_action_manager ' + sel)].find(e => e.getClientRects().length && e.innerText.trim());
        if (el) { el.scrollIntoView({block:'center'}); el.click(); return sel + ' :: ' + el.innerText.trim().slice(0, 40); }
      }
      return '';
    })()`);
}

async function closeDetail(page) {
    await page.send("Input.dispatchKeyEvent", { type: "keyDown", key: "Escape", code: "Escape", windowsVirtualKeyCode: 27 }).catch(() => {});
    await page.send("Input.dispatchKeyEvent", { type: "keyUp", key: "Escape", code: "Escape", windowsVirtualKeyCode: 27 }).catch(() => {});
    await sleep(500);
}

// The handover's main detail drawers: on these screens the first record is opened.
// [path regex, row selector, optional JS to run first (e.g. pick a step so the list shows)]
const DETAILS = [
    [/Con người › Nhân viên$/, ".ppl-card, .ppl-card *, [class*=ppl-row]", "new Promise(r => setTimeout(r, 3000))"],
    [/Con người › Hợp đồng$/, ".ctl-card-top"],
    [/Lương › Các đợt lương$/, ".pbr-card-main"],
    [/Lương › Phiếu lương$/, ".psr-card", "document.querySelector('.pbim-st') && document.querySelector('.pbim-st').click()"],
    [/Trang chủ › Hộp thư/, ".pbam-row, .pbam-card, [class^=pbam-item], [class*=pbam-req]"],
    [/Chi phí › Hoàn chi phí$/, ".o_data_row td.o_data_cell"],
    [/Chi phí › Công tác$/, ".o_data_row td.o_data_cell, [class*=trip-card], [class*=-card-main]"],
];
const detailFor = (p) => DETAILS.find(([rx]) => rx.test(p));

async function main() {
    const page = await openPage(Number(args.port || 9577));
    const secret = fs.readFileSync(args["secret-file"], "utf8");
    const pw = (secret.match(/password `([^`]+)`/) || [])[1];
    if (!pw) throw new Error("no password in secret file");
    await page.goto(BASE + "/web/login");
    const auth = await page.eval(`fetch('/web/session/authenticate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',params:{db:${JSON.stringify(args.db)},login:${JSON.stringify(args.login)},password:${JSON.stringify(pw)}}})}).then(r=>r.json()).then(j=>j.error?('ERR '+j.error.data.message):('uid '+j.result.uid+' lang '+j.result.user_context.lang))`);
    console.log("auth:", auth);
    if (!auth.startsWith("uid")) throw new Error(auth);
    const home = args.home || "/bizapp/action-1156";
    await page.goto(BASE + home);
    await settle(page, 4000);
    await expandSidebar(page);
    let entries = await sidebarEntries(page);
    // expand entries that have sub-entries, then re-read
    for (const e of entries.filter((x) => x.caret)) {
        await page.eval(`(() => { const b=[...document.querySelectorAll('.pb-sidebar .pb-nav-item')].find(x=>x.getAttribute('title')===${JSON.stringify(e.title)}); const c=b&&b.querySelector('.pb-nav-caret:not(.open)'); if(c) c.click(); })()`);
        await sleep(300);
    }
    entries = await sidebarEntries(page);
    console.log("sidebar entries:", entries.map((e) => (e.sub ? "  " : "") + e.title).join(" | "));
    const skipped = [];
    for (const e of entries) {
        if (e.sectionLocked) { skipped.push({ path: e.section, why: "section locked for this user" }); continue; }
        const label = (e.section ? e.section + " › " : "") + e.title;
        if (ONLY && !ONLY.test(label)) continue;
        await page.goto(BASE + home);
        await settle(page, 1500);
        await expandSidebar(page);
        if (e.sub) {
            const parent = entries[entries.indexOf(e) - 1];
            await page.eval(`(() => { for (const b of document.querySelectorAll('.pb-sidebar .pb-nav-caret:not(.open)')) b.click(); })()`);
            await sleep(300);
        }
        const ok = await clickSidebar(page, e.title, e.sub);
        if (!ok) { skipped.push({ path: label, why: "sidebar button not found" }); continue; }
        await settle(page, 3000);
        const tabs = await hubTabs(page);
        // a hub reopens on the tab used last (pbhub.<hub>.lens.v1 in localStorage): select the first
        if (tabs.length) { await clickHubTab(page, 0); await settle(page, 2500); }
        const first = tabs.length ? `${label} › ${tabs[0] || "tab 1"}` : label;
        await record(page, first, tabs.length ? "hubtab" : "screen", { locked: e.locked, tabs });
        await extras(page, first);
        for (let i = 1; i < tabs.length; i++) {
            const p = `${label} › ${tabs[i] || "tab " + (i + 1)}`;
            if (!(await clickHubTab(page, i))) { skipped.push({ path: p, why: "tab not clickable" }); continue; }
            await settle(page, 2500);
            await record(page, p, "hubtab");
            await extras(page, p, i);
        }
    }
    fs.writeFileSync(path.join(OUT, "sweep.json"), JSON.stringify({ base: BASE, entries, skipped, records }, null, 1));
    console.log("done; records", records.length, "skipped", skipped.length);
    page.close();
}

async function extras(page, p, tabIndex = 0) {
    const d = detailFor(p);
    if (d) await detail(page, p, d[1], d[2]);
    if (/Trang chủ › Hộp thư/.test(p)) {
        // the inbox's own tabs (My turn, Waiting, Done...)
        const n = await page.eval(`document.querySelectorAll('.pbam-tab').length`).catch(() => 0);
        for (let i = 1; i < n; i++) {
            const name = await page.eval(`(() => { const b = document.querySelectorAll('.pbam-tab')[${i}]; b.click(); return b.textContent.replace(/\\s+/g,' ').replace(/\\d+$/,'').trim(); })()`);
            await settle(page, 2000);
            await record(page, `${p} › ${name}`, "subtab");
            await detail(page, `${p} › ${name}`, d[1]);
        }
    }
    if (/Cài đặt › /.test(p)) {
        // every card of this Settings section: open, record, come back
        const cards = await page.eval(`[...document.querySelectorAll('.o_action_manager .pbim-btn')].filter(b => b.getClientRects().length).map(b => (b.closest('[class*=card]')?.querySelector('h3,h4,[class*=title],[class*=__t]')?.textContent || b.textContent).replace(/\\s+/g,' ').trim())`).catch(() => []);
        for (let c = 0; c < cards.length; c++) {
            const ok = await page.eval(`(() => { const b = [...document.querySelectorAll('.o_action_manager .pbim-btn')].filter(b => b.getClientRects().length)[${c}]; if (!b) return false; b.click(); return true; })()`);
            if (!ok) continue;
            await settle(page, 3000);
            await record(page, `${p} › ${cards[c] || "card " + (c + 1)}`, "card");
            await page.goto(BASE + (args.home || "/bizapp/action-1156"));
            await settle(page, 1500);
            await clickSidebar(page, "Cài đặt", false);
            await settle(page, 2500);
            await clickHubTab(page, tabIndex);
            await settle(page, 2000);
        }
    }
}

async function detail(page, p, selector, pre) {
    if (pre) { await page.eval(pre).catch(() => {}); await settle(page, 2500); }
    const before = await page.eval("location.pathname + location.hash").catch(() => "");
    const hit = selector ? await page.eval(`(() => {
        const el = [...document.querySelectorAll(${JSON.stringify(selector)})].find(e => e.getClientRects().length && e.innerText.trim());
        if (!el) return ''; el.scrollIntoView({block:'center'}); el.click(); return el.innerText.replace(/\\s+/g,' ').trim().slice(0, 50);
    })()`).catch(() => "") : await openFirstRow(page);
    if (!hit) { records.push({ path: p + " › (detail)", kind: "detail", missing: "no row/card found", texts: [], attrs: [] }); return; }
    await settle(page, 2500);
    await record(page, p + " › (detail)", "detail", { opened: hit });
    await closeDetail(page);
    const after = await page.eval("location.pathname + location.hash").catch(() => "");
    if (after !== before) { await page.eval("history.back()").catch(() => {}); await settle(page, 2000); }
}

main().catch((e) => { console.error(e); try { fs.writeFileSync(path.join(OUT, "sweep.partial.json"), JSON.stringify({ records }, null, 1)); } catch (x) {} process.exit(1); });
