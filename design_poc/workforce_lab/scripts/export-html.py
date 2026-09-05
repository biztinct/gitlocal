from pathlib import Path
import re,html
root=Path(__file__).resolve().parents[1]
source=(root/'research/report-source.md').read_text()
def inline(s):
 s=html.escape(s)
 s=re.sub(r'\[([^\]]+)\]\((https://[^)]+)\)',r'<a href="\2" target="_blank" rel="noopener">\1</a>',s)
 return re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',s)
out=[]; table=False
for line in source.splitlines():
 if line.startswith('|'):
  if re.match(r'^\|[\s|:-]+$',line): continue
  if not table: out.append('<div class="compare-wrap"><table>');table=True
  out.append('<tr>'+''.join('<td>'+inline(c.strip())+'</td>' for c in line.strip('|').split('|'))+'</tr>');continue
 if table: out.append('</table></div>');table=False
 if not line.strip():continue
 if line.startswith('#'): n=len(line)-len(line.lstrip('#'));out.append(f'<h{n}>'+inline(line[n:].strip())+f'</h{n}>')
 else:out.append('<p>'+inline(line)+'</p>')
if table:out.append('</table></div>')
(root/'public/research.html').write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Research & recommendation | Workforce Futures</title><link rel="stylesheet" href="styles.css"></head><body><main class="research-body"><a href="index.html">← Back to the concepts</a><div class="research-links"><a href="cockpit.html">01 Cockpit</a><a href="guide.html">02 Guided Path</a><a href="studio.html">03 Coverage Studio</a></div>'+''.join(out)+'</main></body></html>')
css=(root/'app/globals.css').read_text().replace("@import 'tailwindcss';",'')
cards=[('01','The What-if Cockpit','START HERE · RECOMMENDED','Move a slider. See the whole business respond. Understand the cost, capacity and profit behind every people decision.','cockpit','mint','Explore the cockpit'),('02','The Guided Path','FOR A FIRST-TIME PLANNER','Start with an ambition. Find practical ways to get there, understand the trade-offs, and build your plan one decision at a time.','guide','lilac','Find a path'),('03','The Coverage Studio','FOR SHIFT-BASED OPERATIONS','See where the work and the people don’t line up. Rebalance shifts and watch coverage, overtime and your bottom line change together.','studio','peach','Balance the workforce')]
cardhtml=''
for n,name,tag,desc,href,tone,action in cards:
 bars=''.join(f'<i style="height:{v}%"></i>' for v in [34,48,43,63,57,78,85,93])
 cardhtml+=f'<a class="concept {tone}" href="{href}.html"><div class="card-top"><span>{n}</span><span class="eyebrow">{tag}</span><span>↗</span></div><div class="mini-chart" aria-hidden="true">{bars}</div><h2>{name}</h2><p>{desc}</p><strong>{action}<span>→</span></strong></a>'
(root/'public/index.html').write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Workforce Futures | Payobook Design Lab</title><meta name="description" content="Three interactive concepts for intuitive workforce planning."><meta property="og:title" content="Workforce Futures"><meta property="og:description" content="Better people decisions, beautifully simple."><meta property="og:image" content="https://payobook-workforce-futures.groovy-pixie-4012.chatgpt.site/og.png"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="Workforce Futures"><meta name="twitter:description" content="Better people decisions, beautifully simple."><meta name="twitter:image" content="https://payobook-workforce-futures.groovy-pixie-4012.chatgpt.site/og.png"><style>'+css+'</style></head><body><main class="gallery"><header><a class="brand" href="index.html">p<span>payobook</span></a><span class="eyebrow">DESIGN LAB / WORKFORCE PLANNING</span><span class="pill">Interactive concepts · 2026</span></header><section class="intro"><span class="eyebrow">BETTER PEOPLE DECISIONS, BEAUTIFULLY SIMPLE.</span><h1>What if your next people decision<br><em>was your clearest one?</em></h1><p>Three ways to explore the future of your workforce.<br>Real interactions. Connected outcomes. Room to think.</p><div class="intro-note"><span class="dot"></span>Fictional mixed workforce · USD · No live employee data</div></section><section class="concept-grid">'+cardhtml+'</section><section class="recommendation"><span class="eyebrow">OUR RECOMMENDATION</span><h2>One product. Three natural ways in.</h2><p>Make the Cockpit the everyday home, offer the Guided Path when someone needs a starting point, and open the Coverage Studio when a decision needs operational detail.</p><a href="research.html">Read the research & design recommendation →</a></section><footer><span>Payobook · Workforce Futures</span><span>Proof of concept — explore, compare, choose.</span></footer></main></body></html>')
