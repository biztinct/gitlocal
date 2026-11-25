#!/bin/bash
# WFSETUP P7: custom modules (not in the server's odoo git clone) of pb_workforce_setup's dependency
# closure, read from the LIVE addons dir. Root, read-only: bash p7_closure.sh
python3 - <<'PY'
import ast, os, subprocess
add = "/odoo/odoo-server/addons"
def deps(m):
    p = os.path.join(add, m, "__manifest__.py")
    return ast.literal_eval(open(p).read()).get("depends", []) if os.path.exists(p) else []
seen, todo = set(), ["pb_workforce_setup"]
while todo:
    for d in deps(todo.pop()):
        if d not in seen:
            seen.add(d); todo.append(d)
std = set(subprocess.run("git -C /odoo/odoo-server ls-files addons | cut -d/ -f2 | sort -u", shell=True,
                         capture_output=True, text=True).stdout.split())
print(" ".join(sorted(m for m in seen | {"pb_workforce_setup"} if m not in std and os.path.isdir(os.path.join(add, m)))))
PY
