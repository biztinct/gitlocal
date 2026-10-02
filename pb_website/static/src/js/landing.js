/* Payobook homepage: progressive enhancement, accessible previews and canvas globe. */
(function () {
  "use strict";
  function boot() {
    var root = document.querySelector('.pb_landing');
    if (!root || root.dataset.initialized) return;
    root.dataset.initialized = 'true';
    document.title = 'Payobook — Intelligent Global Payroll';
    var reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
    var menu = root.querySelector('.pb-menu'), nav = root.querySelector('#pb-navigation');
    if (!menu || !nav) return; // An older cached homepage may still be in flight during an upgrade.
    function closeMenu() { nav.classList.remove('is-open'); menu.setAttribute('aria-expanded','false'); menu.setAttribute('aria-label','Open navigation'); }
    menu.addEventListener('click',function () {
      var open = !nav.classList.contains('is-open');
      nav.classList.toggle('is-open',open); menu.setAttribute('aria-expanded',String(open));
      menu.setAttribute('aria-label',open ? 'Close navigation' : 'Open navigation');
    });
    root.addEventListener('keydown',function (e) { if (e.key === 'Escape' && nav.classList.contains('is-open')) { closeMenu(); menu.focus(); } });
    root.querySelectorAll('a[href^="#"]').forEach(function (link) {
      link.addEventListener('click',function (e) {
        var target = root.querySelector(link.getAttribute('href'));
        if (!target) return;
        e.preventDefault(); closeMenu();
        target.scrollIntoView({behavior: reduced.matches ? 'auto' : 'smooth', block:'start'});
        history.replaceState(null,'',link.getAttribute('href'));
        // Preserve keyboard access after skip navigation without changing tab order.
        if (link.classList.contains('pb-skip')) { target.setAttribute('tabindex','-1'); target.focus({preventScroll:true}); }
      });
    });
    function accessibleTabs(container, callback) {
      var tabs = Array.from(container.querySelectorAll('[role="tab"]'));
      function select(tab) {
        tabs.forEach(function (item) { var active = item === tab; item.setAttribute('aria-selected',String(active)); item.tabIndex = active ? 0 : -1; });
        callback(tab);
      }
      tabs.forEach(function (tab,i) {
        tab.addEventListener('click',function () { select(tab); });
        tab.addEventListener('keydown',function (e) {
          var next;
          if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next = (i+1)%tabs.length;
          else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = (i+tabs.length-1)%tabs.length;
          else if (e.key === 'Home') next = 0;
          else if (e.key === 'End') next = tabs.length-1;
          if (next !== undefined) { e.preventDefault(); select(tabs[next]); tabs[next].focus(); }
        });
      });
    }
    var ai = {
      analytics: {question:'How is our payroll changing across countries?',title:'Seven countries.\nOne clear perspective.',answer:'Compare payroll costs across your region, then explore the people and departments behind the change.',chart:'Payroll distribution',note:'USD equivalent',insight:'Go beyond the total. Understand the drivers.',bars:[84,56,46,67,38,28,18]},
      summary: {question:'Give me a clear summary of this pay period.',title:'The numbers,\nin plain language.',answer:'Payroll rose 3.1% this period, mainly from new hires. Singapore remains the largest share of regional payroll. Review the key movements before approval.',chart:'Regional payroll at a glance',note:'Example period',insight:'An executive summary you can take into the conversation.',bars:[84,56,46,67,38,28,18]},
      pulse: {question:'What needs my attention before I approve?',title:'See the change.\nKnow where to look.',answer:'The illustrative run shows an unusual increase in overtime in Vietnam. Review the underlying entries and confirm the reason before signing off.',chart:'Changes flagged for review',note:'Illustrative signals',insight:'A focused review starts with the right questions.',bars:[16,22,18,87,12,32,14]},
      forecast: {question:'What could our payroll look like next period?',title:'Look ahead.\nPlan with perspective.',answer:'Explore projected payroll costs using recent trends and planned headcount. Compare scenarios to understand how team growth could affect your next period.',chart:'Illustrative next-period projection',note:'Scenario, not a guarantee',insight:'Make planning conversations more informed.',bars:[88,69,50,75,44,31,21]}
    };
    function text(id,value) { root.querySelector('#'+id).textContent = value; }
    accessibleTabs(root.querySelector('.pb-ai-tabs'),function (tab) {
      var data = ai[tab.dataset.ai];
      text('pb-ai-question',data.question); text('pb-ai-title',data.title); text('pb-ai-answer',data.answer);
      root.querySelector('.pb-bars').setAttribute('aria-label',data.chart+' — illustrative preview');
      text('pb-ai-chart-title',data.chart); text('pb-ai-chart-note',data.note); text('pb-ai-insight',data.insight);
      root.querySelector('#pb-ai-panel').setAttribute('aria-labelledby',tab.id);
      root.querySelectorAll('.pb-bars > div').forEach(function (bar,i) { bar.style.setProperty('--bar',data.bars[i]+'%'); });
    });
    var countries = {
      SG:['Singapore','Bring CPF contributions and local payroll levies into your pay run, with clear visibility from calculation to review.',['CPF','SDL','FWL']],
      IN:['India','Connect salary structures with Provident Fund, Professional Tax and TDS calculations in a guided payroll workflow.',['Provident Fund','Professional Tax','TDS']],
      MY:['Malaysia','Bring statutory contributions and monthly tax deductions together with your salary components.',['EPF','SOCSO','EIS','PCB']],
      VN:['Vietnam','Connect personal income tax with social, health and unemployment insurance calculations and statutory reporting.',['PIT','BHXH','BHYT','BHTN']],
      ID:['Indonesia','Bring income tax and social insurance components into a connected payroll experience.',['PPh 21','BPJS Kesehatan','BPJS Ketenagakerjaan']],
      TH:['Thailand','Connect local income tax and Social Security Fund contributions to your payroll calculations.',['Income Tax','SSF','Provident Fund']],
      KH:['Cambodia','Bring local salary tax and social security components into your country payroll workflow.',['Tax on Salary','NSSF','Fringe benefits']]
    };
    accessibleTabs(root.querySelector('.pb-country-tabs'),function (tab) {
      var code = tab.dataset.country, data = countries[code];
      text('pb-country-code',code); text('pb-country-name',data[0]); text('pb-country-description',data[1]);
      var chips = root.querySelector('#pb-country-chips'); chips.replaceChildren();
      data[2].forEach(function (label) { var chip = document.createElement('span'); chip.textContent = label; chips.appendChild(chip); });
      root.querySelector('#pb-country-panel').setAttribute('aria-labelledby',tab.id);
    });
    var formulas = {
      allowance:['BASIC × ALLOWANCE_RATE','Basic salary','50,000','Allowance rate','20%','10,000','This rule calculates the allowance as 20% of basic salary.'],
      bonus:['BASIC × BONUS_RATE','Basic salary','50,000','Bonus rate','10%','5,000','This rule calculates a bonus as 10% of basic salary.'],
      overtime:['OVERTIME_HOURS × HOURLY_RATE','Overtime hours','12','Hourly rate','250','3,000','This rule multiplies 12 overtime hours by a sample hourly rate of 250.']
    };
    root.querySelectorAll('[data-formula]').forEach(function (btn) {
      btn.addEventListener('click',function () {
        root.querySelectorAll('[data-formula]').forEach(function (other) { other.classList.toggle('is-active',other===btn); other.setAttribute('aria-pressed',String(other===btn)); });
        var data = formulas[btn.dataset.formula];
        ['pb-formula-code','pb-formula-input-label','pb-formula-input','pb-formula-rate-label','pb-formula-rate','pb-formula-result','pb-formula-explanation'].forEach(function (id,i) { text(id,data[i]); });
      });
    });
    // Globe: public-domain Natural Earth land points, projected onto a shaded sphere.
    var canvas = root.querySelector('#pb-globe'), ctx = canvas.getContext('2d');
    if (!ctx) return;
    var land = window.PB_LAND || [], w=0,h=0,visible=true,frame=0,start=performance.now(),last=0;
    var rad = Math.PI/180, angle=105*rad, tilt=19*rad;
    function project(lon,lat,rot) {
      var a=lon*rad-rot, b=lat*rad;
      var x=Math.cos(b)*Math.sin(a), y=Math.sin(b), z=Math.cos(b)*Math.cos(a);
      return [x,y*Math.cos(tilt)-z*Math.sin(tilt),y*Math.sin(tilt)+z*Math.cos(tilt)];
    }
    function size() {
      var rect=canvas.getBoundingClientRect(),dpr=Math.min(devicePixelRatio||1,2);
      w=rect.width;h=rect.height;canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);
      draw(performance.now());
    }
    function draw(now) {
      if (!w || !h) return;
      var t=reduced.matches?0:Math.max(0,(now-start)/1000), rot=angle+Math.sin(t*.065)*.12;
      var cx=w/2,cy=h/2,r=Math.min(w,h)*.345;
      ctx.clearRect(0,0,w,h);
      var glow=ctx.createRadialGradient(cx,cy,r*.8,cx,cy,r*1.5);glow.addColorStop(0,'rgba(131,174,232,.13)');glow.addColorStop(.5,'rgba(107,147,222,.05)');glow.addColorStop(1,'rgba(80,130,210,0)');ctx.fillStyle=glow;ctx.fillRect(0,0,w,h);
      var sphere=ctx.createRadialGradient(cx-r*.45,cy-r*.5,r*.07,cx,cy,r*1.05);sphere.addColorStop(0,'#263d58');sphere.addColorStop(.5,'#162a42');sphere.addColorStop(.85,'#101c30');sphere.addColorStop(1,'#070e1b');ctx.fillStyle=sphere;ctx.beginPath();ctx.arc(cx,cy,r,0,Math.PI*2);ctx.fill();
      function line(points,color,width) {
        ctx.strokeStyle=color;ctx.lineWidth=width;ctx.beginPath();var active=false;
        points.forEach(function (p) { var q=project(p[0],p[1],rot); if(q[2]>.015) { var px=cx+q[0]*r,py=cy-q[1]*r;if(!active)ctx.moveTo(px,py);else ctx.lineTo(px,py);active=true; } else active=false; });ctx.stroke();
      }
      for(var lat=-60;lat<=60;lat+=20) { var row=[];for(var lon=-180;lon<=180;lon+=3)row.push([lon,lat]);line(row,'rgba(169,202,255,.10)',.6); }
      for(var lon2=-180;lon2<180;lon2+=20) { var col=[];for(var lat2=-88;lat2<=88;lat2+=3)col.push([lon2,lat2]);line(col,'rgba(169,202,255,.10)',.6); }
      land.forEach(function (p) { var q=project(p[0],p[1],rot);if(q[2]<=0)return;ctx.fillStyle='rgba(183,216,239,'+(.16+.66*q[2])+')';ctx.beginPath();ctx.arc(cx+q[0]*r,cy-q[1]*r,Math.max(.55,r*.0045)*(.5+.5*q[2]),0,Math.PI*2);ctx.fill(); });
      var nodes=[[103.82,1.35],[77.2,28.6],[101.7,3.14],[105.8,21.03],[106.8,-6.2],[100.5,13.75],[104.9,11.56],[120.98,14.60]];
      // Great-circle flight paths, raised above the globe.
      var origin=nodes[0];nodes.slice(1).forEach(function (p,idx) {
        var u=vec(origin),v=vec(p),dot=Math.max(-1,Math.min(1,u[0]*v[0]+u[1]*v[1]+u[2]*v[2])),omega=Math.acos(dot),arc=[];
        for(var i=0;i<=40;i++){var f=i/40,aa=Math.sin((1-f)*omega)/Math.sin(omega),bb=Math.sin(f*omega)/Math.sin(omega),x=u[0]*aa+v[0]*bb,y=u[1]*aa+v[1]*bb,z=u[2]*aa+v[2]*bb;arc.push([Math.atan2(x,z)/rad,Math.asin(y)/rad,1+Math.sin(f*Math.PI)*.12]);}
        ctx.beginPath();ctx.strokeStyle='rgba(214,252,139,.34)';ctx.lineWidth=.9;arc.forEach(function (p,i){var q=project(p[0],p[1],rot);if(q[2]>0){var x=cx+q[0]*r*p[2],y=cy-q[1]*r*p[2];if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);}});ctx.stroke();
        var pos=arc[Math.floor(((t*.18+idx*.17)%1)*40)],q=project(pos[0],pos[1],rot);if(q[2]>0){ctx.fillStyle='#d6fc8b';ctx.shadowBlur=8;ctx.shadowColor='#d6fc8b';ctx.beginPath();ctx.arc(cx+q[0]*r*pos[2],cy-q[1]*r*pos[2],1.7,0,Math.PI*2);ctx.fill();ctx.shadowBlur=0;}
      });
      nodes.forEach(function (p,i){var q=project(p[0],p[1],rot);if(q[2]<0)return;var x=cx+q[0]*r,y=cy-q[1]*r,pulse=4+((t*.45+i*.2)%1)*10;ctx.strokeStyle='rgba(214,252,139,'+(.3*(1-(pulse-4)/10))+')';ctx.beginPath();ctx.arc(x,y,pulse,0,Math.PI*2);ctx.stroke();ctx.fillStyle='#d6fc8b';ctx.shadowBlur=13;ctx.shadowColor='#d6fc8b';ctx.beginPath();ctx.arc(x,y,2.3,0,Math.PI*2);ctx.fill();ctx.shadowBlur=0;});
      ctx.strokeStyle='rgba(176,213,255,.38)';ctx.lineWidth=1;ctx.beginPath();ctx.arc(cx,cy,r,0,Math.PI*2);ctx.stroke();
    }
    function vec(p){var a=p[0]*rad,b=p[1]*rad;return [Math.cos(b)*Math.sin(a),Math.sin(b),Math.cos(b)*Math.cos(a)];}
    function loop(now) { frame=0;if(!visible||document.hidden||reduced.matches)return;if(now-last>40){draw(now);last=now;}frame=requestAnimationFrame(loop); }
    function resume(){if(frame)cancelAnimationFrame(frame);frame=0;draw(performance.now());if(visible&&!document.hidden&&!reduced.matches)frame=requestAnimationFrame(loop);}
    if('ResizeObserver' in window)new ResizeObserver(size).observe(canvas);else window.addEventListener('resize',size,{passive:true});
    if('IntersectionObserver' in window)new IntersectionObserver(function(entries){visible=entries[0].isIntersecting;resume();},{rootMargin:'100px'}).observe(canvas);
    document.addEventListener('visibilitychange',resume);reduced.addEventListener('change',resume);size();resume();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
