/* WORKFLOW-2 P3a browser checks U2–U8 (stages on the workbench).
   LOCAL DISPOSABLE DATABASE ONLY: it creates workflows and company stages and
   publishes/activates one workflow. It refuses any URL that is not localhost.
   Credentials come from the environment, never from this file:
     WORKFLOW_UI_URL=http://127.0.0.1:8077 WORKFLOW_UI_DB=am_wf2p3 \
     WORKFLOW_UI_LOGIN=… WORKFLOW_UI_PASSWORD=… node tools/workflow_studio/chrome_test_p3a.cjs
   Uses real mouse input (Playwright), so the pointer drag is exercised as a person would. No screenshots are kept. */
const assert=require('assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_PATH||'/Users/adity/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base=process.env.WORKFLOW_UI_URL||'http://127.0.0.1:8077';
if(!/^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/.test(base))throw Error('Local databases only: '+base);
const db=process.env.WORKFLOW_UI_DB,login=process.env.WORKFLOW_UI_LOGIN,password=process.env.WORKFLOW_UI_PASSWORD;
if(!db||!login||!password)throw Error('Set WORKFLOW_UI_DB, WORKFLOW_UI_LOGIN and WORKFLOW_UI_PASSWORD.');
const stamp=Date.now().toString(36);
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 const context=await browser.newContext({viewport:{width:1500,height:950}});
 const page=await context.newPage();const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('console',m=>{if(m.type()==='error'&&!/favicon|\/web\/image\//.test(m.location()?.url||''))errors.push(m.text());});
 const auth=await (await context.request.post(base+'/web/session/authenticate',{data:{jsonrpc:'2.0',method:'call',params:{db,login,password}}})).json();
 assert.ok(auth.result?.uid,'Login failed');
 const open=async q=>{await page.goto(base+'/pb_lifecycle/static/workflow/index.html?v=wf2-p3a2&'+(q||''));await page.locator('.topbar').waitFor();};
 const rpc=(m,a)=>page.evaluate(([m,a])=>rpc(m,a),[m,a]);
 const button=(name,scope=page)=>scope.getByRole('button',{name,exact:true});
 const sheet=page.locator('#sheet');
 try{
  // U2 — create from an expense claim with its own stages
  await open();
  await button('Create workflow').first().click();
  await page.locator('#new-name').fill('P3a check '+stamp);
  await page.locator('#new-model').selectOption('pb.expense.claim');
  await page.locator('#own-stages').waitFor();
  assert.ok(await page.locator('#own-stages').isChecked());
  await button('Create workflow',page.locator('#dialog')).click();
  await page.locator('.journey').waitFor();
  const heads=await page.locator('.journey .stage-head h3').allTextContents();
  assert.deepEqual(heads,['Draft','Waiting approval','Approved','Paid']);
  await page.getByText('If an approver says no, it becomes Refused. Steps after that point do not run.').first().waitFor();
  await button('Review').first().click();
  await page.getByText('The workflow is ready to publish').waitFor();
  assert.equal(await button('Open Stages').count(),0);
  await button('Build').click();
  console.log('PASS U2: own stages, exits note, no binding error');
  // U3 — every view shows what the section is and what already happens
  for(const view of ['Journey','By stage','Across']){
   await button(view).click();
   assert.ok(await page.getByText('Expenses owns this stage').count()>=4,view);
   assert.ok(await page.getByText('Gets here when: the employee sends the claim').count()>=1,view);
  }
  await button('Flowchart').click();
  assert.equal(await page.locator('.stage-label .flow-tag').count(),4);
  const chips=await page.locator('.flow-chip').count();assert.ok(chips>=1);
  console.log('PASS U3: Journey, By stage, Across and Flowchart show stage tags and what already happens');
  // U4 — By stage: add with the column button, move with a real mouse, Undo
  await button('By stage').click();
  const col=i=>page.locator('.stage-column').nth(i);
  await col(1).getByRole('button',{name:'Add a step',exact:true}).click();
  await page.locator('#dialog [data-type="task"]').click();
  await page.getByRole('button',{name:'Close step settings'}).click();
  const card=col(1).locator('.node',{hasText:'Assign a task'});
  await card.waitFor();
  const shape=()=>page.evaluate(()=>{const d=(0,eval)('S').w.definition;return JSON.stringify([d.order,d.nodes.map(n=>[n.id,n.stage])]);});
  const before=await shape();
  await card.dragTo(col(2).locator('.drop').last());
  await page.getByText('Step moved. Undo is available.').waitFor();
  assert.equal(await col(2).locator('.node',{hasText:'Assign a task'}).count(),1);
  await button('Undo').click();
  assert.equal(await shape(),before);
  await button('Redo').click();
  await button('Journey').click();
  const order=await page.locator('.journey .node h3').allTextContents();assert.deepEqual(order,['Start','Assign a task']);
  console.log('PASS U4: column add, real mouse drag between columns, Undo/Redo, Journey agrees');
  // U5 — add a person-moved stage after Approved, a heading, rename, move, refused move
  await button('Stages').click();await sheet.waitFor({state:'visible'});
  await sheet.locator('[data-act="sf-open"][data-at="3"]').click();
  const stageName='P3a booked '+stamp;
  await sheet.locator('#sf-name').fill(stageName);
  await sheet.locator('label.choice-card',{hasText:'A person moves it'}).click();
  await sheet.locator('[data-edit="stageForm.owner.kind"]').selectOption('user');
  await sheet.locator('[data-edit="stageForm.owner.id"]').selectOption({index:1});
  await sheet.locator('#sf-target').selectOption('72');
  await button('Add this stage',sheet).click();
  await sheet.getByText('Your stage · counts as Approved in Expenses').waitFor();
  assert.ok(await sheet.getByText('Target 3 days').count());
  await sheet.locator('[data-act="sf-open"]').last().click();
  await sheet.locator('#sf-name').fill('Wrap up');
  await sheet.locator('label.choice-card',{hasText:'Just a heading'}).click();
  await button('Add this heading',sheet).click();
  await sheet.locator('[data-row="5"] [data-act="heading-rename"]').click();
  await sheet.locator('[data-heading-name="5"]').fill('Close the file');await sheet.locator('[data-heading-name="5"]').press('Enter');
  await sheet.getByText('Close the file',{exact:true}).waitFor();
  await sheet.locator('[data-act="section-up"][data-index="5"]').click();
  assert.equal(await sheet.locator('[data-row="4"] .stage-row-name').textContent(),'Close the file');
  await sheet.locator('[data-act="section-up"][data-index="2"]').click();
  await page.getByText('Expenses’ stages keep their own order.').waitFor();
  await button('Done',sheet).click();
  for(const view of ['Journey','By stage','Across'])await button(view).click(),assert.ok(await page.getByText('Your stage · counts as Approved in Expenses').count());
  console.log('PASS U5: your stage, heading, rename, move, refused move explained');
  // U7 — a stage with steps: move them first, then remove; delete refused while an active workflow uses it
  await button('Stages').click();
  await sheet.locator('[data-act="section-remove"][data-index="2"]').click();
  await sheet.locator('.row-blocked').getByRole('button').click();
  await page.getByText('Steps moved to “Waiting approval”. Undo is available.').waitFor();
  await sheet.locator('[data-act="section-remove"][data-index="2"]').click();
  await page.getByText('“Approved” is no longer used here. Undo is available.').waitFor();
  const cat=await rpc('stage_catalogue',['pb.expense.claim']);const mine=cat.stages.find(s=>s.name===stageName);
  const other=await rpc('create_workflow',['P3a user of '+stamp,'pb.expense.claim','Expenses',false]);
  const full=await rpc('get_workflow',[other.id]);const d=full.definition;d.stages=[{name:'Start'},{name:stageName,bind:{kind:'yours',id:mine.key}}];
  d.nodes.push({id:'t1',type:'task',title:'Book it',stage:1,owner:{kind:'initiator'},due:2});d.order.push('t1');
  const saved=await rpc('save_draft',[other.id,full.revision,d]);await rpc('publish',[other.id,saved.revision,'P3a']);await rpc('activate',[other.id,true,true]);
  const row=sheet.locator('.stage-row',{hasText:stageName});
  await row.getByRole('button',{name:'Delete for everyone'}).click();
  await page.locator('#dialog').getByRole('button',{name:'Delete for everyone'}).click();
  await page.getByText(`“P3a user of ${stamp}” waits for this stage. Pause that workflow or change its sections first.`).waitFor();
  await rpc('activate',[other.id,false]);
  await button('Done',sheet).click();
  console.log('PASS U7: move steps first, remove, delete refused with the server sentence');
  // U6 — three default headings, then "Use all of them"
  const plain=await rpc('create_workflow',['P3a headings '+stamp,'pb.expense.claim','Expenses',false]);
  await open('workflow='+plain.id);
  await button('Stages').click();
  await button('Use all of them',sheet).click();
  const names=await sheet.locator('.stage-row-name').allTextContents();
  assert.deepEqual(names,['Prepare','Do the work','Finish','Draft','Waiting approval','Approved','Paid']);
  await button('Done',sheet).click();
  await button('Review').first().click();await page.getByText('The workflow is ready to publish').waitFor();
  console.log('PASS U6: headings stay, the record’s stages follow, order valid');
  // U8 — a new process: every stage is yours, no area wording
  const proc=await rpc('create_workflow',['P3a process '+stamp,'','Operations',false]);
  await open('workflow='+proc.id);
  await button('Stages').click();
  await sheet.getByText('This is your own process, so every stage is yours.').waitFor();
  for(const [at,name] of [[1,'Ordered'],[2,'Delivered']]){
   await sheet.locator(`[data-act="sf-open"][data-at="${at}"]`).click();
   await sheet.locator('#sf-name').fill(name);
   await button('Add this stage',sheet).click();
   await sheet.locator('.stage-row-name',{hasText:name}).waitFor();
  }
  const text=await page.locator('body').innerText();
  assert.ok(!/owns this stage|counts as/.test(text));
  console.log('PASS U8: new process stages are all yours, no area wording');
  assert.deepEqual(errors,[]);
  console.log('PASS: no page errors');
 }finally{await browser.close();}
})().catch(e=>{console.error('FAIL:',e.message);process.exit(1);});
