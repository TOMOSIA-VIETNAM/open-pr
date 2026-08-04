# Reconfigure a settings node

On request, any time — never wait for the next review/fix run. Triggered by INTENT, not a fixed string
("reconfigure review" / "reconfigure fix" / "change the config" / "show current settings"). `<node>` =
the calling command's own node (`core/repo-settings.md`).

1. `Read` `<node>` of the CURRENT repo's `settings.json`, never the plugin seed. Print EVERY field
   present, 1 line each (name + value); a field bootstrap asks about but that is absent → print it with
   the default that would apply. FORBIDDEN: a hardcoded field-name list — enumerate what actually
   exists, so a field added later needs no edit here.
2. Ask which field(s) + the new value, WAIT for confirmation.
3. `Edit` that exact field inside `<node>`, leaving other fields and foreign nodes untouched. Then
   `core/memory-commit.md`.
