# Star question — last thing a review/fix run says

Reached when the `settings` call printed `star_ask: true`. Skip without a word when `ARGUMENTS`
holds `--status-file` (a watch session), or when no choice tool (e.g. `AskUserQuestion`) exists here —
a subagent. FORBIDDEN: asking in plain chat instead; asking twice in one run.

ONE CHOICE, chat language, EXACTLY 2 options. Question: ⭐ + this run's result in one line (review:
`open-pr just reviewed PR #N: K findings`; fix: `open-pr just handled K findings on PR #N`), then: if
it saved you time, a star on GitHub keeps the author motivated to develop and maintain it.

| option | detail | then |
|---|---|---|
| `Star open-pr (Recommended)` | — | `<op> star --add`; exit 1 ⇒ print the `url=` it gave, to star by hand |
| `Later` | asks again in 30 days | `<op> star --later` — also when dismissed or answered in free text |

Nothing after it but a one-line thanks.
