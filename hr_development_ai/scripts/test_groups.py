u = env["res.users"].search([("login","=","minh.nv")], limit=1)
print("User:", u.name if u else "NOT FOUND")
if u:
    g = env.ref("base.group_user")
    print("Trying group.write...")
    g.write({"users": [(4, u.id)]})
    print("Success! User added to group via group.write")
    env.cr.commit()
    # Now try BFSI group
    try:
        bg = env.ref("hr_development_ai.group_bfsi_branch_manager")
        bg.write({"users": [(4, u.id)]})
        print("BFSI BM group added successfully")
        env.cr.commit()
    except Exception as e:
        print(f"BFSI group error: {e}")

# Check kpi target fields
t = env["bfsi.kpi.target"]
flds = sorted([f for f in t._fields.keys()])
print("KPI Target fields:", flds)
