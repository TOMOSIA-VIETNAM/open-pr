# Asking which language — `output_language` + `chat_language` alike

Read ONLY when one of them has to be ASKED; a field already set never reaches here.

NO fixed menu: `.shared.chat_language` when set, else the detection chain of
`core/repo-settings.md` "`chat_language`", `(Recommended)` + English + Other free text; neither ⇒
English alone. An `output_language` pick NEVER writes `chat_language`. Store BCP-47 codes (`pt`, not
`Portuguese`); multi-script ⇒ pin the script, asking when unknown: Chinese `zh-Hans` || `zh-Hant`,
never bare `zh`.
