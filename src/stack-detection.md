# Stack detection

Maps each file in the diff to the applicable review stack(s). A PR can mix multiple stacks; keep a
list of `(file, [applicable stacks])` pairs, do not assign a single stack to the whole PR when its
files belong to different stacks.

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
| `.md` that is instructions for an AI agent, not documentation for a human reader (see the note below the table) | `agent-instructions` |

_Detecting `agent-instructions`: judged by CONTENT, not just the file extension — imperative,
action-directing tone, not a narrative for a human reader. Illustrative example paths/filenames,
not an exhaustive list: `.claude/commands/`, `.claude/skills/`, `.cursor/rules/`, `CLAUDE.md`,
`AGENTS.md`, `*.cursorrules`, `copilot-instructions.md`._

## Overlays (added on top of a base stack, not a replacement)

- **Lambda** — path contains `lambda`/`lambdas`/`functions/`, OR the repo has `serverless.yml` /
  `template.yaml` / `sam.yaml`, OR a filename `handler.py`/`handler.js`/`index.py`/`index.js` sits
  next to one of the config files above → add `lambda-common` on top of `python` (for `.py` files)
  or `nodejs` (for `.js`/`.ts` files).
- **Laravel** — repo has `artisan`, `composer.json` contains `laravel/framework`, or the path is
  `app/Http/Controllers`, `resources/views/*.blade.php` → add `laravel` on top of `php`.
- **WordPress** — repo has `wp-config.php`, path `wp-content/plugins/` or `wp-content/themes/`, or
  `style.css` has a theme header → add `wordpress` on top of `php`.
