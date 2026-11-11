/* WORKFLOW-2 P3b browser checks (U1 drag/click/"+", U7 Duplicate + Undo, U9 keyboard).
   LOCAL DISPOSABLE DATABASE ONLY: it creates draft workflows. It refuses any
   URL that is not localhost. Credentials come from the environment:
     WORKFLOW_UI_URL=http://127.0.0.1:8097 WORKFLOW_UI_DB=am_wf2p3b \
     WORKFLOW_UI_LOGIN=… WORKFLOW_UI_PASSWORD=… node tools/workflow_studio/chrome_test_p3b.cjs
   Real mouse input (Playwright), so the pointer drag runs as a person's would. */
const assert=require('assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_PATH||'/Users/adity/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base=process.env.WORKFLOW_UI_URL||'http://127.0.0.1:8097';
if(!/^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/.test(base))throw Error('Local databases only: '+base);
const db=process.env.WORKFLOW_UI_DB,login=process.env.WORKFLOW_UI_LOGIN,password=process.env.WORKFLOW_UI_PASSWORD;
if(!db||!login||!password)throw Error('Set WORKFLOW_UI_DB, WORKFLOW_UI_LOGIN and WORKFLOW_UI_PASSWORD.');
const NEW=['stage_move','send_back','update','create','notify','confirm','start','end'];
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 const context=await browser.newContext({viewport:{width:1500,height:950}});
 const page=await context.newPage();const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('console',m=>{if(m.type()==='error'&&!/favicon|\/web\/image\//.test(m.location()?.url||''))errors.push(m.text());});
 const auth=await (await context.request.post(base+'/web/session/authenticate',{data:{jsonrpc:'2.0',method:'call',params:{db,login,password}}})).json();
 assert.ok(auth.result?.uid,'Login failed');
 await page.goto(base+'/pb_lifecycle/static/workflow/index.html?v=wf2-p3b');await page.locator('.topbar').waitFor();
 const types=()=>page.evaluate(()=>(0,eval)('S').w.definition.nodes.map(n=>n.type));
 const count=async t=>(await types()).filter(x=>x===t).length;
 const report=[];
 try{
  const w=await page.evaluate(()=>rpc('create_workflow',['P3b drag '+Date.now().toString(36),'pb.expense.claim','Expenses']));
  await page.evaluate(id=>openWorkflow(id),w.id);await page.locator('.journey').waitFor();
  // U1 by drag in Journey: every new step type, each onto the last "+" of the main path.
  await page.locator('.palette details[data-more] > summary').click();
  for(const t of NEW){
   const before=await count(t);
   await page.locator(`.palette [data-drag-type="${t}"]`).dragTo(page.locator('.journey .drop').last());
   await page.waitForTimeout(250);
   assert.equal(await count(t),before+1,'journey drag '+t);
   assert.ok(await page.locator('.palette details[data-more]').evaluate(d=>d.open),'More possibilities stays open');
  }
  report.push('U1 Journey drag: 8/8');
  // By stage: drag two of them into a column's slot.
  await page.locator('.viewbar [data-act="view"][data-id="stage"]').click();
  for(const t of ['notify','confirm']){const before=await count(t);await page.locator(`.palette [data-drag-type="${t}"]`).dragTo(page.locator('.stage-board .drop').first());await page.waitForTimeout(250);assert.equal(await count(t),before+1,'by stage drag '+t);}
  report.push('U1 By stage drag: 2/2');
  // Canvas.
  await page.locator('.viewbar [data-act="view"][data-id="flow"]').click();
  for(const t of ['update','start']){const before=await count(t);await page.locator(`.palette [data-drag-type="${t}"]`).dragTo(page.locator('.canvas .drop').nth(1));await page.waitForTimeout(250);assert.equal(await count(t),before+1,'canvas drag '+t);}
  report.push('U1 canvas drag: 2/2');
  // Click and "+".
  await page.locator('.viewbar [data-act="view"][data-id="journey"]').click();
  {const before=await count('end');await page.locator('.palette [data-act="add"][data-type="end"]').click();await page.waitForTimeout(250);assert.equal(await count('end'),before+1,'click add');}
  {const before=await count('send_back');await page.locator('.journey .drop').first().click();await page.locator('#dialog [data-act="add-picked"][data-type="send_back"]').click();await page.waitForTimeout(250);assert.equal(await count('send_back'),before+1,'plus add');}
  report.push('U1 click + "+": ok');
  // Each inspector opens without an error.
  for(const t of NEW){await page.evaluate(t=>{const S=(0,eval)('S');S.selected=S.w.definition.nodes.find(n=>n.type===t).id;render();},t);await page.locator('.drawer').waitFor();assert.ok((await page.locator('.drawer').innerText()).length>40,'inspector '+t);}
  report.push('U2 inspectors open: 8/8');
  // U7 Duplicate then Undo (a step and its order come back exactly).
  const snap=()=>page.evaluate(()=>{const d=(0,eval)('S').w.definition;return JSON.stringify([d.order,d.nodes.map(n=>n.id)]);});
  const before=await snap();
  await page.locator('.drawer [data-act="duplicate"]').click();await page.waitForTimeout(300);
  assert.notEqual(await snap(),before,'duplicate changed nothing');
  assert.match(await page.locator('.drawer [data-edit="title"]').inputValue(),/\(copy\)$/);
  await page.locator('.editor-head [data-act="undo"]').click();await page.waitForTimeout(400);
  assert.equal(await snap(),before,'undo restores');
  report.push('U7 Duplicate + Undo: ok');
  // U9 keyboard: reach the notice step settings and set its recipient with keys only.
  await page.evaluate(()=>{const S=(0,eval)('S');S.selected=S.w.definition.nodes.find(n=>n.type==='notify').id;render();});
  await page.locator('.drawer [data-edit="title"]').focus();
  let reached=false;for(let i=0;i<12;i++){await page.keyboard.press('Tab');if(await page.evaluate(()=>document.activeElement?.id==='notify-text')){reached=true;break;}}
  assert.ok(reached,'notice text reachable by Tab');
  await page.keyboard.type('Booked for payment.');await page.keyboard.press('Tab');
  assert.equal(await page.evaluate(()=>(0,eval)('S').w.definition.nodes.find(n=>n.type==='notify').text),'Booked for payment.');
  report.push('U9 keyboard (notice): ok');
  assert.deepEqual(errors,[],'page errors');
  report.push('no page errors');
  console.log(report.join('\n'));
 }catch(e){console.log(report.join('\n'));console.log('FAILED',e.message,errors);process.exitCode=1;}
 finally{await browser.close();}
})();
