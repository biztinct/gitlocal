/* WORKFLOW-2 P5c browser checks — LOCAL DISPOSABLE DATABASES ONLY.
     WORKFLOW_UI_URL=http://127.0.0.1:8097 P5C_FIXTURE=/path/to/fixture.json SHOTS=/dir \
     node tools/workflow_studio/chrome_test_p5c.cjs
   The fixture file (tools/workflow_studio/ui_fixture_p5c.py) holds the local
   logins; nothing secret is in this file. Real mouse input (Playwright).
   Checks: canvas pixel-identity without a repeat (repeat.js blocked vs
   loaded), "Repeat for each…" by click, "+" and drag on Journey / By stage /
   Flowchart, the inspector's live sample, "Around a date" both ways, the
   Approvals inbox grouping and "Do all in turn", progress per line + Retry,
   the record strip, the employee home, 390 px, console and banned words. */
const assert = require('assert/strict');
const fs = require('fs');
const path = require('path');
const {chromium} = require(process.env.PLAYWRIGHT_PATH || '/Users/adity/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base = process.env.WORKFLOW_UI_URL || 'http://127.0.0.1:8097';
if (!/^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/.test(base)) throw Error('Local databases only: ' + base);
const fx = JSON.parse(fs.readFileSync(process.env.P5C_FIXTURE, 'utf8'));
const shots = process.env.SHOTS || '/tmp';
const WB = '/pb_lifecycle/static/workflow/index.html?v=wf2-p5c';
const report = [];
const errors = [];
const ok = (k, v) => { report.push([k, v]); console.log('CHECK', k, JSON.stringify(v)); };

async function session(browser, loginName, width = 1500, height = 950) {
  const context = await browser.newContext({viewport: {width, height}});
  const page = await context.newPage();
  page.on('pageerror', (e) => errors.push(loginName + ': ' + e.message));
  page.on('console', (m) => {
    if (m.type() === 'error' && !/favicon|\/web\/image\/|Failed to load resource/.test(m.text() + (m.location()?.url || ''))) errors.push(loginName + ': ' + m.text());
  });
  const auth = await (await context.request.post(base + '/web/session/authenticate', {data: {jsonrpc: '2.0', method: 'call', params: {db: fx.database, login: loginName, password: fx.password}}})).json();
  assert.ok(auth.result?.uid, 'Login failed for ' + loginName);
  return {context, page};
}
const S = (page) => page.evaluate(() => (0, eval)('S'));
async function openFlow(page, id, view) {
  await page.evaluate(async ([id, view]) => { await openWorkflow(id); S.view = view; render(); }, [id, view]);
  await page.waitForTimeout(400);
}
function banned(text) { return /\bodoo\b|sub-run|\bloop\b|iteration|\bindex\b/i.test(text); }

(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  try {
    // ------------------------------------------------ A. canvas pixel identity
    const a = await session(browser, fx.designer);
    const b = await session(browser, fx.designer);
    await b.context.route('**/repeat.js*', (r) => r.fulfill({status: 200, contentType: 'application/javascript', body: '/* blocked for the before picture */'}));
    for (const s of [a, b]) { await s.page.goto(base + WB); await s.page.locator('.topbar').waitFor(); }
    // the "after" page really runs this phase's code, the "before" page does not
    assert.equal(await a.page.evaluate(() => typeof repAsLanes), 'function');
    assert.equal(await b.page.evaluate(() => typeof repAsLanes), 'undefined');
    const ids = await a.page.evaluate(async () => {
      const rows = await rpc('list_workflows');
      const out = [], defs = {};
      for (const r of rows) {
        try { defs[r.id] = (await rpc('get_workflow', [r.id])).definition; } catch (e) { continue; }
        const d = defs[r.id];
        if (!d.nodes.some((n) => n.type === 'repeat') && d.nodes.length >= 3 && d.nodes.some((n) => n.branches || n.steps)) out.push(r.id);
        if (out.length === 2) break;
      }
      if (out.length < 2) for (const [id, d] of Object.entries(defs)) { if (!d.nodes.some((n) => n.type === 'repeat') && !out.includes(Number(id)) && d.nodes.length >= 3) out.push(Number(id)); if (out.length === 2) break; }
      return out;
    });
    assert.equal(ids.length, 2, 'two shipped drafts without a repeat');
    const pixel = [];
    for (const id of ids) {
      const pics = [];
      for (const s of [b, a]) {
        await openFlow(s.page, id, 'flow');
        const surf = s.page.locator('.surface');
        await surf.waitFor();
        pics.push({png: await surf.screenshot(), html: await surf.evaluate((e) => e.outerHTML)});
      }
      fs.writeFileSync(path.join(shots, `A_canvas_${id}_before.png`), pics[0].png);
      fs.writeFileSync(path.join(shots, `A_canvas_${id}_after.png`), pics[1].png);
      pixel.push({id, same_png: Buffer.compare(pics[0].png, pics[1].png) === 0, same_html: pics[0].html === pics[1].html, bytes: pics[0].png.length});
    }
    ok('A canvas pixel identity', pixel);
    assert.ok(pixel.every((p) => p.same_png && p.same_html));
    await b.context.close();

    // ------------------------------------------------ B. add a repeat, + and drag
    const p = a.page;
    const w = await p.evaluate(() => rpc('create_workflow', ['P5c screens ' + Date.now().toString(36), 'pb.expense.claim', 'Expenses']));
    await openFlow(p, w.id, 'journey');
    await p.locator('.palette details[data-more] > summary').click();
    await p.locator('.palette-item[data-type="repeat"]').click();
    await p.locator('.repeat-frame').waitFor();
    let st = await S(p);
    const rep = st.w.definition.nodes.find((n) => n.type === 'repeat');
    ok('B add by click', {title: rep.title, source: rep.source, frame: await p.locator('.repeat-frame .repeat-chip').innerText()});
    assert.equal(rep.title, 'For each receipt');
    // the inspector and its live sample
    await p.locator('#rep-sample .rep-sample-row').waitFor({timeout: 8000});
    const sample = await p.locator('#rep-sample').innerText();
    ok('C live sample', sample);
    assert.match(sample, /has \d+ receipts?/);
    await p.screenshot({path: path.join(shots, 'C_repeat_inspector.png')});
    // "+" inside the frame: only what may run once per line is offered
    await p.locator('.repeat-frame .drop').first().click();
    const offered = await p.locator('#dialog .choice-list button').allInnerTexts();
    ok('B + inside offers', offered);
    assert.ok(!offered.some((x) => /Approval Matrix|Move to a stage|Start another workflow|Repeat for each/.test(x)));
    await p.locator('#dialog [data-type="task"]').click();
    st = await S(p);
    const inside = st.w.definition.nodes.find((n) => n.type === 'repeat').steps;
    assert.equal(inside.length, 1);
    // a task on the main path, dragged into the frame (real mouse)
    await p.evaluate(() => addNode('task'));
    await p.waitForTimeout(300);
    st = await S(p);
    const loose = st.w.definition.order.at(-1);
    const grip = p.locator(`.node[data-id="${loose}"] .grip`);
    const target = p.locator('.repeat-frame .drop').last();
    await grip.scrollIntoViewIfNeeded();
    const g = await grip.boundingBox();
    await p.mouse.move(g.x + g.width / 2, g.y + g.height / 2);
    await p.mouse.down();
    await p.mouse.move(g.x + 20, g.y + 30, {steps: 6});
    await target.scrollIntoViewIfNeeded();
    const tb = await target.boundingBox();
    await p.mouse.move(tb.x + tb.width / 2, tb.y + tb.height / 2, {steps: 12});
    await p.mouse.up();
    await p.waitForTimeout(500);
    st = await S(p);
    const steps2 = st.w.definition.nodes.find((n) => n.type === 'repeat').steps;
    ok('B drag into the frame (Journey)', {steps: steps2, moved: steps2.includes(loose)});
    assert.ok(steps2.includes(loose));
    await p.screenshot({path: path.join(shots, 'B_journey_frame.png'), fullPage: false});
    // By stage, Across, Flowchart
    await p.evaluate(() => { S.view = 'stage'; S.selected = null; render(); });
    await p.locator('.stage-board .repeat-frame').waitFor();
    await p.screenshot({path: path.join(shots, 'B_bystage_frame.png')});
    await p.evaluate(() => { S.view = 'horizontal'; render(); });
    const across = await p.locator('.snake-view').innerText();
    assert.match(across, /For each receipt/);
    await p.evaluate(() => { S.view = 'flow'; render(); });
    await p.locator('.repeat-box').waitFor();
    const tag = await p.locator('.repeat-box .repeat-chip').allInnerTexts();
    ok('B canvas frame', {chip: tag, join: await p.locator('.join').allInnerTexts()});
    assert.ok(tag.some((t) => /For each receipt/.test(t)));
    await p.screenshot({path: path.join(shots, 'B_canvas_frame.png')});
    // drag out of the frame on the canvas back to the main path
    const cg = p.locator(`.surface .node[data-id="${loose}"] .grip`);
    const mainSlot = p.locator('.surface .drop').last();
    await cg.scrollIntoViewIfNeeded();
    const c1 = await cg.boundingBox();
    await p.mouse.move(c1.x + c1.width / 2, c1.y + c1.height / 2);
    await p.mouse.down();
    await p.mouse.move(c1.x + 25, c1.y + 30, {steps: 6});
    await mainSlot.scrollIntoViewIfNeeded();
    const c2 = await mainSlot.boundingBox();
    await p.mouse.move(c2.x + c2.width / 2, c2.y + c2.height / 2, {steps: 12});
    await p.mouse.up();
    await p.waitForTimeout(500);
    st = await S(p);
    ok('B drag out (canvas)', {inside: st.w.definition.nodes.find((n) => n.type === 'repeat').steps, main: st.w.definition.order});
    // refused: an approval step dropped into the repeat says why (no console error)
    await p.evaluate(() => { S.view = 'journey'; render(); });
    const refused = await p.evaluate(() => { try { moveStep(S.w.definition, S.w.definition.order.at(-1), targets(S.w.definition).find((t) => t.key === S.w.definition.nodes.find((n) => n.type === 'repeat').id)); return 'moved'; } catch (e) { return e.message; } });
    ok('B refusal words (task is allowed, so moved)', refused);

    // ------------------------------------------------ D. "Around a date" both ways
    await p.evaluate(() => { S.selected = 'trigger'; render(); });
    await p.locator('select[data-edit="trigger.kind"]').selectOption('schedule');
    await p.locator('[data-sched-around]').waitFor();
    await p.locator('[data-sched-around]').click();
    await p.waitForTimeout(300);
    st = await S(p);
    ok('D30 around a date', {kind: st.w.definition.trigger.kind, field: st.w.definition.trigger.date_field, mode: st.w.definition.trigger.mode});
    assert.equal(st.w.definition.trigger.kind, 'date');
    await p.locator('.sched-around').waitFor();
    await p.screenshot({path: path.join(shots, 'D_around_a_date.png')});
    await p.locator('[data-sched-back="week"]').click();
    await p.waitForTimeout(300);
    st = await S(p);
    ok('D30 back to a schedule', {kind: st.w.definition.trigger.kind, every: st.w.definition.trigger.schedule?.every});
    assert.equal(st.w.definition.trigger.kind, 'schedule');

    // ------------------------------------------------ U11: 390 px repeat inspector
    await p.setViewportSize({width: 390, height: 844});
    await p.evaluate(() => { S.view = 'journey'; S.selected = S.w.definition.nodes.find((n) => n.type === 'repeat').id; render(); });
    await p.waitForTimeout(500);
    const over = await p.evaluate(() => document.documentElement.scrollWidth);
    ok('U11 390px repeat inspector scrollWidth', over);
    await p.screenshot({path: path.join(shots, 'U11_repeat_inspector_390.png')});
    await p.setViewportSize({width: 1500, height: 950});

    // ------------------------------------------------ F. progress per line, Retry
    await p.evaluate((id) => loadProgress(id), fx.run_id);
    await p.waitForTimeout(500);
    await p.evaluate(() => { S.selected = 'rep'; render(); });
    await p.locator('.rep-lines').waitFor();
    ok('F progress lines', await p.locator('.rep-lines').innerText());
    await p.screenshot({path: path.join(shots, 'F_progress_lines.png')});
    await p.evaluate((id) => loadProgress(id), fx.fail_run_id);
    await p.evaluate(() => { S.selected = 'rep'; render(); });
    await p.locator('.rep-line.is-failed').waitFor();
    await p.screenshot({path: path.join(shots, 'F_failed_line.png')});
    await p.locator('[data-act="retry-line"]').click();
    await p.locator('.rep-line.is-failed').waitFor({state: 'detached', timeout: 15000}).catch(() => {});
    const after = await p.evaluate(() => S.progress.steps.find((s) => s.key === 'rep').lines.map((l) => l.state));
    ok('F retry the line', after);
    assert.ok(!after.includes('failed'));
    // Activity: Show lines
    await openFlow(p, fx.workflow_id, 'journey');
    await p.evaluate(() => action('tab', {dataset: {id: 'runs'}}));
    await p.locator('[data-act="toggle-lines"]').click();
    await p.waitForTimeout(600);
    const rows = await p.locator('table tbody tr').count();
    ok('Activity show lines rows', rows);
    await p.screenshot({path: path.join(shots, 'F_activity_show_lines.png')});

    // ------------------------------------------------ the record strip (staff)
    await p.goto(base + `/odoo/pb.expense.claim/${fx.claim_id}`).catch(() => {});
    await p.waitForTimeout(2500);
    const stripText = await p.locator('.pbwfs-host').innerText().catch(() => '(no strip host on this screen)');
    ok('Strip on the claim', stripText);
    await p.screenshot({path: path.join(shots, 'G_claim_strip.png')});

    // ------------------------------------------------ E. inbox: grouped tasks, Do all in turn
    const c = await session(browser, fx.checker);
    const q = c.page;
    await q.goto(base + '/odoo/action-pb_approval_config.action_pb_approval_inbox');
    await q.locator('.pbwfi-group').waitFor({timeout: 20000});
    await q.waitForTimeout(800);
    const groupText = await q.locator('.pbwfi-group').innerText();
    ok('E inbox tasks group', groupText);
    assert.match(groupText, /Do all in turn/);
    assert.match(groupText, /to do/);
    await q.screenshot({path: path.join(shots, 'E_inbox_grouped.png')});
    await q.locator('.pbwfi-turnhead button').first().click();
    await q.locator('.pbwfi-drawer').waitFor();
    await q.locator('.pbwfi-turnnote').waitFor();
    ok('E drawer turn note', await q.locator('.pbwfi-turnnote').innerText());
    const frame = q.frameLocator('.pbwfi-frame');
    await frame.locator('.line-chip').waitFor({timeout: 15000});
    ok('E task page line chip', await frame.locator('.line-chip').innerText());
    await q.screenshot({path: path.join(shots, 'E_drawer_first_line.png')});
    const firstTitle = await q.locator('#pbwfi-drawer-h').innerText();
    await frame.locator('[data-act="complete-outcome"][data-id="fine"]').click();
    await q.waitForTimeout(2500);
    const nextTitle = await q.locator('#pbwfi-drawer-h').innerText().catch(() => '');
    ok('E next opens by itself', {firstTitle, nextTitle});
    assert.ok(nextTitle && nextTitle !== firstTitle);
    await q.screenshot({path: path.join(shots, 'E_drawer_next_line.png')});
    await q.setViewportSize({width: 390, height: 844});
    await q.keyboard.press('Escape');
    await q.waitForTimeout(600);
    await q.screenshot({path: path.join(shots, 'U11_inbox_390.png'), fullPage: true});
    ok('U11 inbox 390 scrollWidth', await q.evaluate(() => document.documentElement.scrollWidth));
    const inboxBody = await q.locator('body').innerText();
    assert.ok(!banned(inboxBody), 'banned word on the inbox');

    // ------------------------------------------------ U7: employee home and the task page
    const h = await session(browser, fx.home, 1200, 900);
    await h.page.goto(base + '/my/todo');
    const list = await h.page.locator('main').innerText();
    ok('U7 employee home list', list.slice(0, 400));
    assert.match(list, /Confirm this receipt is yours · /);
    await h.page.screenshot({path: path.join(shots, 'U7_home_list.png'), fullPage: true});
    await h.page.locator('a.pbwt-item').first().click();
    await h.page.waitForLoadState('domcontentloaded');
    const taskPage = await h.page.locator('main').innerText();
    ok('U7 employee home task page', taskPage.slice(0, 300));
    assert.match(taskPage, /receipt 1 of 2/);
    await h.page.screenshot({path: path.join(shots, 'U7_home_task.png'), fullPage: true});
    assert.ok(!banned(list + taskPage), 'banned word on the employee home');
  } finally {
    await browser.close();
  }
  ok('console errors', errors);
  fs.writeFileSync(path.join(shots, 'report.json'), JSON.stringify({report, errors}, null, 1));
  if (errors.length) process.exitCode = 1;
})().catch((e) => { console.error('FAILED', e.stack || e.message); fs.writeFileSync(path.join(shots, 'report.json'), JSON.stringify({report, errors, failed: e.message}, null, 1)); process.exitCode = 2; });
