# The upstream migration index

`llm-upgrades/index.md` lives in this plugin's own repo, never inside the installed plugin — fetch it
live over raw HTTP:

```
curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/llm-upgrades/index.md
```

Same base URL for a `vN.md`. Raw HTTP, not `gh api`: the plugin's own repo is on GitHub whatever vendor
the user's PRs are on, and a GitLab-only user has no `gh` to authenticate. `-f` makes a 404 a non-zero
exit instead of an HTML page parsed as an index.

Every entry is one line, `- vN: <ADDED|MODIFIED|REMOVED|RENAMED> <summary> — llm-upgrades/vN.md`. A
version appears ONLY because it required a config migration, so the highest `N` present always equals
the current schema shape, never a gap.
