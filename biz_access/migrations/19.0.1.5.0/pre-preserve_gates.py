def migrate(cr, version):
    # Existing menu decisions must survive the reverse-dependency data reload.
    # New entries still receive their shipped defaults normally.
    cr.execute("ALTER TABLE pb_sidebar_item ADD COLUMN IF NOT EXISTS access_customized boolean DEFAULT false")
    cr.execute("UPDATE pb_sidebar_item SET access_customized=true")
