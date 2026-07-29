# Stack detection

Keep a `(file, [stacks])` pair per diff file. A PR mixes stacks — FORBIDDEN: 1 stack for the whole PR
when its files differ.

## Base stack mapping table — file extension / path

| File condition | Stack |
|---|---|
| `.rb`, `.erb`, `.haml` | `rails` |
| `.vue` | `vue` |
| `.jsx`, `.tsx` (not `.vue`; supporting heuristic: path contains `src/components`, `pages/`, or the file imports `react`) | `react` |
| `.py` | `python` |
| remaining `.js`, `.ts` (not `.vue` / `.jsx` / `.tsx` / the FE directories above) | `nodejs` |
| `.sh`, `.bash` | `shell` |
| `Makefile`, `makefile`, `*.mk` | `makefile` |
| `.php` (not caught by the Laravel/WordPress overlays below) | `php` |
| `.md` whose content instructs an AI agent rather than documenting for a human | `agent-instructions` |

_Judged by CONTENT, never extension alone: imperative text aimed at a model, not a narrative for a
human. Illustrative paths: `.claude/commands/`, `.claude/skills/`, `.cursor/rules/`, `CLAUDE.md`,
`AGENTS.md`, `*.cursorrules`, `copilot-instructions.md`._

## Overlays (added on top of a base stack, never replacing it)

Any 1 signal is enough.

| overlay | signals | on top of |
|---|---|---|
| `lambda-common` | path has `lambda`/`lambdas`/`functions/` · repo has `serverless.yml`/`template.yaml`/`sam.yaml` · a `handler.py`/`handler.js`/`index.py`/`index.js` sits next to one of those configs | `python` (`.py`) or `nodejs` (`.js`/`.ts`) |
| `laravel` | repo has `artisan` · `composer.json` contains `laravel/framework` · path `app/Http/Controllers` or `resources/views/*.blade.php` | `php` |
| `wordpress` | repo has `wp-config.php` · path `wp-content/plugins/` or `wp-content/themes/` · `style.css` carries a theme header | `php` |
| `agent-instructions` | prompt text inside code/config/data: a multi-line string/heredoc/template literal instructing a model · a `SYSTEM_PROMPT`/`INSTRUCTIONS`-style name · a `system`/`instructions` key in YAML/JSON · a `role: system` message payload · a `prompts/` or `*.prompt.*` path | that file's base stack — code reviewed as code, prompt as prompt |
