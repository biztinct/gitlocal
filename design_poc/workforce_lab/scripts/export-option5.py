from pathlib import Path
import re
root=Path(__file__).resolve().parents[1]
public=root/'public'
source=(public/'option5.html').read_text()
source=source.replace('<link rel="stylesheet" href="option5.css">','<style>'+(public/'option5.css').read_text()+'</style>')
source=re.sub(r'<script src="([^"]+)"></script>',lambda m:'<script>'+ (public/m.group(1)).read_text().replace('</script','<\\/script') +'</script>',source)
origin='https://payobook-workforce-futures.groovy-pixie-4012.chatgpt.site/'
source=re.sub(r'href="((?:index|cockpit|guide|studio|living|option5|research)\.html)"',lambda m:'href="'+origin+m.group(1)+'"',source)
(public/'option5-standalone.html').write_text(source)
