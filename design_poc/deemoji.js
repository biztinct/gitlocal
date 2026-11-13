// Replace emojis with PB.icon('name',size) calls inside JS-template option files.
// Composite (with variation selector U+FE0F) keys are listed BEFORE their base glyph.
const fs = require('fs');
const map = [
  ['🗓️', "calendar,16"], ['🏗️', "layers,16"], ['🛡️', "shield,16"], ['⚠️', "alert,15"],
  ['🏠', "home,16"], ['🧾', "receipt,15"], ['⚡', "zap,15"], ['📥', "download,15"],
  ['⬆', "upload,15"], ['👥', "users,16"], ['📄', "file-text,15"], ['🧮', "calculator,16"],
  ['📊', "bar-chart,16"], ['📈', "trending-up,16"], ['✅', "clipboard-check,16"],
  ['🔐', "lock,16"], ['🧭', "compass,16"], ['💰', "wallet,16"], ['💵', "banknote,16"],
  ['⏳', "clock,16"], ['⚠', "alert,14"], ['🖨', "printer,14"], ['↻', "refresh,14"],
  ['＋', "plus,14"], ['✨', "sparkles,15"], ['🏢', "building,16"], ['🧠', "brain,16"],
  ['🔎', "search,16"], ['🔍', "search,15"], ['🗂️', "folder,30"], ['🧩', "puzzle,30"],
  ['✉', "mail,15"], ['🧱', "layers,16"],
];
const file = process.argv[2];
let s = fs.readFileSync(file, 'utf8');
for (const [e, v] of map) {
  const [name, size] = v.split(',');
  s = s.split(e).join("${PB.icon('" + name + "'," + size + ")}");
}
fs.writeFileSync(file, s);
console.log('de-emojified', file);
