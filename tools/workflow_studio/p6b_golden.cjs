/* WORKFLOW-2 P6b — the Studio editor's English is unchanged (golden files)
   and the Vietnamese / Indonesian screens — LOCAL DISPOSABLE DATABASES ONLY.

     WORKFLOW_UI_URL=http://127.0.0.1:8079 P6B_FIXTURE=/path/fixture.json \
       WB_DIR=/dir/with/workbench/files MODE=capture LANG_KEY=en_US OUT=/tmp/golden-new.json \
       node tools/workflow_studio/p6b_golden.cjs
     node tools/workflow_studio/p6b_golden.cjs compare /tmp/golden-old.json /tmp/golden-new.json

   capture: signs in as the fixture's login for LANG_KEY, serves the
   workbench's own files from WB_DIR (the pre-phase files or this phase's —
   no browser cache in the way, ledger G17), and walks every surface: the
   workflow list, My tasks, Activity, a progress page, a task page, and for
   every workflow the five views (Journey, By stage, Across, Flowchart,
   People), the inspector of every step and of the start, Try it out,
   Review, Activity, the Stages sheet and Settings. Each surface's rendered
   DOM (the app plus any open dialog or sheet) is written to OUT. With
   SHOTS=dir it also writes screenshots (WIDTH, default 1280) of a chosen
   set, and with PIXELS=1 a PNG of the four canvases of two drafts for the
   pixel comparison. Fails on console errors.
   compare: equal key sets, equal DOM per key; prints the first difference. */
const assert = require('assert/strict');
const fs = require('fs');
const path = require('path');

if (process.argv[2] === 'compare') {
  const a = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
  const b = JSON.parse(fs.readFileSync(process.argv[4], 'utf8'));
  const ka = Object.keys(a.dom), kb = Object.keys(b.dom);
  let bad = 0;
  // A run's "Updated <day>, <time>" moves when the worker touches it between two captures.
  const norm = (x) => x.replace(/Updated \d{1,2} \w{3} \d{4}, \d{1,2}:\d{2}/g, 'Updated <time>');
  for (const d of [a.dom, b.dom]) for (const k of Object.keys(d)) d[k] = norm(d[k]);
  for (const k of new Set([...ka, ...kb])) {
    if (!(k in a.dom) || !(k in b.dom)) { console.log('MISSING', k, k in a.dom ? 'only in first' : 'only in second'); bad++; continue; }
    if (a.dom[k] !== b.dom[k]) {
      bad++;
      const x = a.dom[k], y = b.dom[k];
      let i = 0; while (i < x.length && x[i] === y[i]) i++;
      console.log('DIFF', k, '\n  first : …' + x.slice(Math.max(0, i - 120), i + 160) + '\n  second: …' + y.slice(Math.max(0, i - 120), i + 160));
    }
  }
  const pa = a.pixels || {}, pb = b.pixels || {};
  let pixels = 0, pbad = 0;
  for (const k of Object.keys(pa)) { pixels++; if (pa[k] !== pb[k]) { pbad++; console.log('PIXELS DIFFER', k); } }
  console.log(`GOLDEN surfaces=${ka.length} differ=${bad} canvases=${pixels} pixel_diff=${pbad}`);
  process.exit(bad || pbad ? 1 : 0);
}

const {chromium} = require(process.env.PLAYWRIGHT_PATH || '/Users/adity/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const crypto = require('crypto');
const base = process.env.WORKFLOW_UI_URL || 'http://127.0.0.1:8079';
if (!/^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/.test(base)) throw Error('Local databases only: ' + base);
const fx = JSON.parse(fs.readFileSync(process.env.P6B_FIXTURE, 'utf8'));
const wbDir = process.env.WB_DIR;
const lang = process.env.LANG_KEY || 'en_US';
const shots = process.env.SHOTS || '';
const width = Number(process.env.WIDTH || 1280);
const errors = [];
const TYPES = {js: 'application/javascript', css: 'text/css', html: 'text/html', woff2: 'font/woff2'};

(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  const context = await browser.newContext({viewport: {width, height: 900}, locale: 'en-GB', timezoneId: 'Asia/Ho_Chi_Minh'});
  const auth = await (await context.request.post(base + '/web/session/authenticate', {data: {jsonrpc: '2.0', method: 'call', params: {db: fx.database, login: fx.logins[lang], password: fx.password}}})).json();
  assert.ok(auth.result?.uid, 'Login failed');
  if (wbDir) await context.route('**/pb_lifecycle/static/workflow/**', (route) => {
    const file = path.join(wbDir, new URL(route.request().url()).pathname.split('/').pop());
    if (!fs.existsSync(file)) return route.fulfill({status: 404, body: ''});
    route.fulfill({status: 200, body: fs.readFileSync(file), contentType: TYPES[file.split('.').pop()] || 'application/octet-stream'});
  });
  await context.addInitScript(() => {
    window.__pending = 0;
    const f = window.fetch;
    window.fetch = (...a) => { window.__pending++; return f(...a).finally(() => { window.__pending--; }); };
    // Dates on screen read "now": pin it so two runs minutes apart render alike.
  });
  const page = await context.newPage();
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => { if (m.type() === 'error' && !/favicon|Failed to load resource/.test(m.text())) errors.push(m.text()); });
  const settle = async () => {
    for (let i = 0; i < 100; i++) {
      await page.waitForTimeout(120);
      const busy = await page.evaluate(() => window.__pending > 0 || !!document.querySelector('[data-pending]'));
      if (!busy) { await page.waitForTimeout(350); if (!(await page.evaluate(() => window.__pending > 0))) return; }
    }
  };
  const dom = {};
  const grab = async (key) => {
    await settle();
    dom[key] = await page.evaluate(() => {
      const parts = [document.querySelector('#app')?.innerHTML || ''];
      for (const id of ['dialog', 'sheet']) { const d = document.getElementById(id); if (d?.open) parts.push('<' + id + '>' + d.innerHTML); }
      return parts.join('\n');
    });
  };
  const run = (fn, ...args) => page.evaluate(fn, ...args);
  const t0 = Date.now();
  await page.goto(`${base}/pb_lifecycle/static/workflow/index.html?v=p6b-golden&company=${fx.company_id}`);
  await page.waitForFunction(() => { try { return !!(0, eval)('S').boot && !document.querySelector('main.loading'); } catch (e) { return false; } }, null, {timeout: 60000});
  const firstPaint = Date.now() - t0;
  await grab('home');
  const shot = async (name) => { if (shots) await page.screenshot({path: path.join(shots, `${lang.slice(0, 2)}_${width}_${name}.png`), fullPage: false}); };
  await shot('home');
  await run(() => action('tasks', {dataset: {}}));
  await grab('tasks'); await shot('tasks');
  await run(() => action('activity', {dataset: {}}));
  await grab('activity'); await shot('activity');
  await run((id) => loadProgress(id), fx.run_id);
  await grab('progress'); await shot('progress');
  if (fx.tasks?.[lang]) {
    const no = await run((id) => openTask(id).then(() => '', (e) => e.message), fx.tasks[lang]);
    if (no) dom.task = 'refused: ' + no; else { await grab('task'); await shot('task'); }
  }
  const ids = await run(() => (0, eval)('S').boot.workflows.map((w) => w.id));
  const pixels = {};
  const shotSet = new Set(Object.values(fx.workflows).slice(0, 3));
  for (const id of ids) {
    const refused = await run((x) => openWorkflow(x).then(() => '', (e) => e.message), id);
    if (refused) { dom[`w${id}.refused`] = refused; await run(() => { (0, eval)('S').page = 'home'; render(); }); continue; }
    await settle();
    const nodes = await run(() => (0, eval)('S').w.definition.nodes.map((n) => n.id));
    for (const view of ['journey', 'stage', 'horizontal', 'flow', 'people']) {
      await run((v) => action('view', {dataset: {id: v}}), view);
      await grab(`w${id}.view.${view}`);
      if (shotSet.has(id)) await shot(`w${id}_${view}`);
      if (process.env.PIXELS && Object.values(fx.workflows).slice(0, 2).includes(id) && view !== 'people') {
        const buf = await page.locator('.workarea').screenshot();
        pixels[`w${id}.${view}`] = crypto.createHash('sha1').update(buf).digest('hex');
      }
    }
    await run(() => action('view', {dataset: {id: 'journey'}}));
    for (const n of nodes) {
      await run((x) => action('node', {dataset: {id: x}, closest: () => null}), n);
      await grab(`w${id}.inspector.${n}`);
      if (shotSet.has(id) && shots) await shot(`w${id}_inspector_${n}`);
    }
    await run(() => action('deselect', {dataset: {}}));
    for (const tab of ['try', 'review', 'runs']) {
      await run((t) => action('tab', {dataset: {id: t}}), tab);
      await grab(`w${id}.tab.${tab}`);
      if (shotSet.has(id)) await shot(`w${id}_${tab}`);
    }
    await run(() => action('tab', {dataset: {id: 'build'}}));
    await run(() => action('stages', {dataset: {}}));
    await grab(`w${id}.stages`);
    if (shotSet.has(id)) await shot(`w${id}_stages`);
    await run(() => { const s = document.getElementById('sheet'); if (s?.open) s.close(); });
    await run(() => action('settings', {dataset: {}}));
    await grab(`w${id}.settings`);
    if (shotSet.has(id)) await shot(`w${id}_settings`);
    await run(() => { const s = document.getElementById('dialog'); if (s?.open) s.close(); });
  }
  const clipped = await page.evaluate(() => [...document.querySelectorAll('button, .pill, .chip, label')].filter((e) => e.offsetParent && e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflow !== 'visible').map((e) => e.textContent.trim().slice(0, 60)).slice(0, 20));
  fs.writeFileSync(process.env.OUT, JSON.stringify({lang, width, first_paint_ms: firstPaint, dom, pixels, clipped, errors}));
  console.log(`CAPTURED ${Object.keys(dom).length} surfaces, first paint ${firstPaint} ms, console errors ${errors.length}`);
  for (const e of errors.slice(0, 10)) console.log('  ERROR', e);
  await browser.close();
  process.exit(errors.length ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
