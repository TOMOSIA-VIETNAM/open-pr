# Install

Claude Code is the platform this plugin is built and tested on. Cursor, Codex, Gemini CLI and
Antigravity run the same review from the same files — they only enter through a different door, which
is what this page is about.

Whatever the platform, you also need [`gh`](https://cli.github.com/) for GitHub PRs or
[`glab`](https://gitlab.com/gitlab-org/cli) for GitLab MRs, installed and logged in. The review is
posted through that account.

## One command

Every platform, Claude Code included:

```bash
curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh | bash
```

It asks which platform you are on, or takes it up front:

```bash
curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh | bash -s -- --platform cursor
```

That script does nothing itself: it puts a clone in `~/.open-pr` at the latest release tag and hands
over to `~/.open-pr/scripts/install-local.sh`, which is the code that installs. Read it there
afterwards — it is what ran, and `--uninstall --all` undoes it.

The release tag pins the clone, not this one line: `install.sh` is fetched from the default branch,
so it is the newest version of the fetcher. Pin that too by pointing the URL at a tag instead of
`main`.

Prefer not to run a script off the internet? The two-step below is the same thing with the reading
in the middle, and the rest of this page is what each platform ends up with.

## Which door

Every platform offers two, and both use a loading mechanism the platform itself documents. They differ
in how the files get to your machine:

- **Catalog** — the platform's own plugin/extension installer, pointed at this repository. It follows
  the default branch, so updating is a command in the platform.
- **Local** — you clone this repository and run `scripts/install-local.sh`. Use it when the catalog
  route is closed to you: a submission still pending review, or an import your account is not
  permitted to do. It stays on the release you cloned until you pull.

| Platform | Catalog | Local | Status |
| -------- | ------- | ----- | ------ |
| Claude Code | `claude plugin marketplace add` + `claude plugin install`, or the slash pair | `--platform claude` | tested |
| Cursor IDE | import this repo as a team marketplace (admin, Teams/Enterprise) | `scripts/install-local.sh --platform cursor` | untested |
| Cursor CLI (`cursor-agent`) | — | `scripts/install-local.sh --platform cursor-cli` | untested |
| Codex | `codex plugin marketplace add` + `/plugins` | `scripts/install-local.sh` | untested |
| Gemini CLI | `gemini extensions install <repo URL>` | `scripts/install-local.sh` | untested |
| Antigravity | `agy plugin install <path>` (CLI only) | `scripts/install-local.sh` | untested |

`tested` means a real review ran end to end and was graded against `e2e/checklist.md`. `untested`
means the files and manifests are in place and match what the platform documents, but nobody has run
a review through that platform yet — treat it as experimental and check the review it posts before
trusting it. If you do run one, the result is worth an issue either way.

## Claude Code

From a shell, without opening a session:

```bash
claude plugin marketplace add TOMOSIA-VIETNAM/open-pr
claude plugin install open-pr@open-pr
```

Or from inside a session:

```bash
/plugin marketplace add TOMOSIA-VIETNAM/open-pr
/plugin install open-pr@open-pr
```

Update, either way:

```bash
claude plugin update open-pr@open-pr    # or /plugin update open-pr@open-pr
/reload-plugins
/open-pr:upgrade
```

Commands arrive namespaced: `/open-pr:review`, `/open-pr:fix`, `/open-pr:upgrade`, `/open-pr:clean`.

## Cursor

The IDE and the CLI do not load the same things. Skills bundled inside a plugin are reported not to
reach `cursor-agent`, only the IDE, so the CLI needs the skills installed on their own:

```bash
~/.open-pr/scripts/install-local.sh --platform cursor-cli   # skills in ~/.cursor/skills
```

For the IDE:

Catalog: in the Cursor dashboard, go to Settings → Plugins → Team Marketplaces → Import and paste this
repository's URL. Cursor reads `.cursor-plugin/marketplace.json` and tracks the default branch from
then on. Creating a team marketplace is an admin action on Teams and Enterprise plans, so on a
personal account use the local route below.

Local: `scripts/install-local.sh --platform cursor` covers both. The IDE gets the whole plugin under
`~/.cursor/plugins/local/open-pr`, the directory Cursor reserves for exactly this, so it appears in
the plugin list with a toggle like any other — reload the window afterwards
(`Developer: Reload Window`). The CLI gets the skills of its own, per the paragraph above.

Either way the four commands show up as `/open-pr-review`, `/open-pr-fix`, `/open-pr-upgrade`,
`/open-pr-clean`.

## Codex

From the shell:

```bash
codex plugin marketplace add TOMOSIA-VIETNAM/open-pr
codex
```

Then `/plugins` inside Codex to install and enable it. The same two steps exist as slash commands if
you are already in a session:

```
/plugin marketplace add TOMOSIA-VIETNAM/open-pr
/plugin install open-pr
/reload-plugins
```

Codex reads the catalog from `.agents/plugins/marketplace.json` in this repository. Publishing to
OpenAI's own plugin directory is a separate, optional channel and is not required to install.

Codex invokes skills explicitly with `$`: `$open-pr-review <PR URL>`.

## Gemini CLI

```bash
gemini extensions install https://github.com/TOMOSIA-VIETNAM/open-pr
```

Update:

```bash
gemini extensions update open-pr
```

This is the one platform that installs straight from a git repository with no catalog in between. It
picks up both the commands (`/review`, `/fix`, `/upgrade`, `/clean`, namespaced by the extension) and
the same four skills.

## Antigravity

The CLI and the IDE read skills from different places, so which one you use decides the route.

CLI (`agy`) — install the plugin:

```bash
git clone https://github.com/TOMOSIA-VIETNAM/open-pr ~/.open-pr
agy plugin install ~/.open-pr
```

IDE — it has no plugin installer, so use the local route, which writes to the directory the IDE reads
globally (`~/.gemini/config/skills`):

```bash
~/.open-pr/scripts/install-local.sh --platform antigravity   # covers the CLI's directory too
```

Either way skills become slash commands: `/open-pr-review` and the other three.

## Local install

For Cursor, Codex, Gemini CLI and Antigravity, when the catalog route is not available to you:

```bash
git clone https://github.com/TOMOSIA-VIETNAM/open-pr ~/.open-pr
~/.open-pr/scripts/install-local.sh
```

Same result as the one-liner, with the script in front of you before it runs.

By default it installs the four skills into `~/.agents/skills/`, which Codex and Gemini CLI both read,
so one run covers both. The other two platforms have a place of their own:

```bash
~/.open-pr/scripts/install-local.sh --platform cursor        # the IDE's plugin dir and the CLI's skills dir
~/.open-pr/scripts/install-local.sh --platform antigravity   # the CLI's skills dir and the IDE's
```

A vendor's IDE and CLI read different directories, so those two names cover both of theirs. Want one
only: `cursor-ide`, `cursor-cli`, `antigravity-cli`, `antigravity-ide`.

Several at once, comma-separated or repeated, and `all` for every platform except Claude Code:

```bash
~/.open-pr/scripts/install-local.sh --platform cursor,shared
~/.open-pr/scripts/install-local.sh --platform all
```

Leave `--platform` out and it asks: Claude Code · Codex or Gemini CLI · Cursor · Antigravity · none
of these. Answer with several numbers (`2 3`) to take more than one, or an empty line to exit having
written nothing. One bad number and it stops before installing anything. Other flags: `--target DIR` to install anywhere else, `--copy` if
your platform will not follow symlinks, `--update` to pull this clone and reinstall in one step,
`--uninstall` to remove what it installed — add `--all` to that and it sweeps every platform above,
so installing in four places still takes one command to undo.

macOS and Linux only: it makes symlinks, which on Windows need developer mode or an elevated shell.

What lands is a symlink back into the clone, so updating every platform at once is:

```bash
git -C ~/.open-pr pull
```

With `--copy` there are no links, so a pull needs the script run again. Either way the script never
touches a file it did not create: if something is already sitting where a skill or the plugin would
go, it stops and tells you, and `--uninstall` leaves that file alone too. A `--copy` install of the
whole plugin carries tracked files only — no `.git`, nothing untracked.

## Adding a platform changes nothing about your repos

`/open-pr:upgrade` (or `$open-pr-upgrade`, `/open-pr-upgrade`) is about the per-repo config the review
writes under `notebooks/review/`. Installing on a second platform does not migrate, move or duplicate
any of it: all platforms read the same config, and there is no migration to run. See
[Configuration](./configuration.md) for what that config holds.
