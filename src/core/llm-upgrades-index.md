# The upstream migration index

`llm-upgrades/index.md` lives in this plugin's own repo, never inside the installed plugin — fetch it
live:

```
gh api --paginate repos/TOMOSIA-VIETNAM/open-pr/contents/llm-upgrades/index.md --jq '.content' |
base64 --decode
```

Every entry is one line, `- vN: <ADDED|MODIFIED|REMOVED|RENAMED> <summary> — llm-upgrades/vN.md`. A
version appears ONLY because it required a config migration, so the highest `N` present always equals
the current schema shape, never a gap.
