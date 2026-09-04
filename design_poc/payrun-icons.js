/* Payobook POC — Lucide icon sprite (MIT). Inject once; use via
   <svg class="ic"><use href="#i-name"/></svg>.  No emoji anywhere. */
(function () {
  var S = {
    check: "<path d='M20 6 9 17l-5-5'/>",
    x: "<path d='M18 6 6 18M6 6l12 12'/>",
    play: "<polygon points='6 3 20 12 6 21 6 3'/>",
    printer: "<path d='M6 9V2h12v7'/><path d='M6 18H4a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2h-2'/><rect x='6' y='14' width='12' height='8' rx='1'/>",
    mail: "<rect width='20' height='16' x='2' y='4' rx='2'/><path d='m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7'/>",
    send: "<path d='m22 2-7 20-4-9-9-4Z'/><path d='M22 2 11 13'/>",
    undo: "<path d='M3 7v6h6'/><path d='M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13'/>",
    refresh: "<path d='M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8'/><path d='M21 3v5h-5'/><path d='M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16'/><path d='M8 16H3v5'/>",
    download: "<path d='M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4'/><polyline points='7 10 12 15 17 10'/><line x1='12' x2='12' y1='15' y2='3'/>",
    calendar: "<path d='M8 2v4M16 2v4'/><rect width='18' height='18' x='3' y='4' rx='2'/><path d='M3 10h18'/>",
    layers: "<path d='M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.57 3.9a2 2 0 0 0 1.66 0l8.57-3.9a1 1 0 0 0 0-1.83Z'/><path d='M2 12.18a1 1 0 0 0 .6.91l8.57 3.91a2 2 0 0 0 1.66 0l8.57-3.9a1 1 0 0 0 .6-.92'/><path d='M2 17.18a1 1 0 0 0 .6.91l8.57 3.91a2 2 0 0 0 1.66 0l8.57-3.9a1 1 0 0 0 .6-.92'/>",
    hash: "<line x1='4' x2='20' y1='9' y2='9'/><line x1='4' x2='20' y1='15' y2='15'/><line x1='10' x2='8' y1='3' y2='21'/><line x1='16' x2='14' y1='3' y2='21'/>",
    search: "<circle cx='11' cy='11' r='8'/><path d='m21 21-4.3-4.3'/>",
    sliders: "<line x1='21' x2='14' y1='4' y2='4'/><line x1='10' x2='3' y1='4' y2='4'/><line x1='21' x2='12' y1='12' y2='12'/><line x1='8' x2='3' y1='12' y2='12'/><line x1='21' x2='16' y1='20' y2='20'/><line x1='12' x2='3' y1='20' y2='20'/><line x1='14' x2='14' y1='2' y2='6'/><line x1='8' x2='8' y1='10' y2='14'/><line x1='16' x2='16' y1='18' y2='22'/>",
    columns: "<rect width='18' height='18' x='3' y='3' rx='2'/><path d='M9 3v18M15 3v18'/>",
    star: "<polygon points='12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2'/>",
    chevronr: "<path d='m9 18 6-6-6-6'/>",
    chevronl: "<path d='m15 18-6-6 6-6'/>",
    home: "<path d='m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z'/><path d='M9 22V12h6v10'/>",
    grid: "<rect width='7' height='7' x='3' y='3' rx='1'/><rect width='7' height='7' x='14' y='3' rx='1'/><rect width='7' height='7' x='14' y='14' rx='1'/><rect width='7' height='7' x='3' y='14' rx='1'/>",
    list: "<line x1='8' x2='21' y1='6' y2='6'/><line x1='8' x2='21' y1='12' y2='12'/><line x1='8' x2='21' y1='18' y2='18'/><line x1='3' x2='3.01' y1='6' y2='6'/><line x1='3' x2='3.01' y1='12' y2='12'/><line x1='3' x2='3.01' y1='18' y2='18'/>",
    zap: "<polygon points='13 2 3 14 12 14 11 22 21 10 12 10 13 2'/>",
    checksquare: "<path d='m9 11 3 3L22 4'/><path d='M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11'/>",
    receipt: "<path d='M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z'/><path d='M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8'/><path d='M12 17.5v-11'/>",
    users: "<path d='M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2'/><circle cx='9' cy='7' r='4'/><path d='M22 21v-2a4 4 0 0 0-3-3.87'/><path d='M16 3.13a4 4 0 0 1 0 7.75'/>",
    filetext: "<path d='M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z'/><path d='M14 2v4a2 2 0 0 0 2 2h4'/><path d='M16 13H8M16 17H8M10 9H8'/>",
    trending: "<polyline points='22 7 13.5 15.5 8.5 10.5 2 17'/><polyline points='16 7 22 7 22 13'/>",
    calculator: "<rect width='16' height='20' x='4' y='2' rx='2'/><line x1='8' x2='16' y1='6' y2='6'/><line x1='16' x2='16' y1='14' y2='18'/><path d='M16 10h.01M12 10h.01M8 10h.01M12 14h.01M8 14h.01M12 18h.01M8 18h.01'/>",
    shield: "<path d='M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1Z'/>",
    barchart: "<line x1='12' x2='12' y1='20' y2='10'/><line x1='18' x2='18' y1='20' y2='4'/><line x1='6' x2='6' y1='20' y2='16'/>",
    alert: "<path d='m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z'/><path d='M12 9v4M12 17h.01'/>",
    arrowr: "<path d='M5 12h14M12 5l7 7-7 7'/>",
    arrowl: "<path d='M19 12H5M12 19l-7-7 7-7'/>",
    eye: "<path d='M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z'/><circle cx='12' cy='12' r='3'/>"
  };
  var parts = '';
  for (var k in S) parts += "<symbol id='i-" + k + "' viewBox='0 0 24 24'>" + S[k] + "</symbol>";
  var holder = document.createElement('div');
  holder.style.cssText = 'position:absolute;width:0;height:0;overflow:hidden';
  holder.innerHTML = "<svg xmlns='http://www.w3.org/2000/svg'>" + parts + "</svg>";
  (document.body || document.documentElement).insertBefore(holder, (document.body || document.documentElement).firstChild);
})();
