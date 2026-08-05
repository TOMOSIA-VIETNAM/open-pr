# Install

Claude Code is the platform this plugin is built and tested on. Cursor, Codex, Gemini CLI and
Antigravity run the same review from the same files — they only enter through a different door, which
is what this page is about.

Whatever the platform, you also need [`gh`](https://cli.github.com/) for GitHub PRs or
[`glab`](https://gitlab.com/gitlab-org/cli) for GitLab MRs, installed and logged in. The review is
posted through that account.

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
| Claude Code | `/plugin marketplace add` + `/plugin install` | not needed | tested |
| Cursor | import this repo as a team marketplace (admin, Teams/Enterprise) | `scripts/install-local.sh` | untested |
| Codex | `codex plugin marketplace add` + `/plugins` | `scripts/install-local.sh` | untested |
| Gemini CLI | `gemini extensions install <repo URL>` | `scripts/install-local.sh` | untested |
| Antigravity | `agy plugin install <path>` | `scripts/install-local.sh` | untested |

`tested` means a real review ran end to end and was graded against `e2e/checklist.md`. `untested`
means the files and manifests are in place and match what the platform documents, but nobody has run
a review through that platform yet — treat it as experimental and check the review it posts before
trusting it. If you do run one, the result is worth an issue either way.

## Claude Code

```bash
/plugin marketplace add TOMOSIA-VIETNAM/open-pr
/plugin install open-pr@open-pr
```

Update:

```bash
/plugin marketplace update open-pr
/plugin update open-pr@open-pr
/reload-plugins
/open-pr:upgrade
```

Commands arrive namespaced: `/open-pr:review`, `/open-pr:fix`, `/open-pr:upgrade`, `/open-pr:clean`.

## Cursor

Catalog: in the Cursor dashboard, go to Settings → Plugins → Team Marketplaces → Import and paste this
repository's URL. Cursor reads `.cursor-plugin/marketplace.json` and tracks the default branch from
then on. Creating a team marketplace is an admin action on Teams and Enterprise plans, so on a
personal account use the local route below.

Local: `scripts/install-local.sh --platform cursor` puts the whole plugin under
`~/.cursor/plugins/local/open-pr`, the directory Cursor reserves for exactly this, so it appears in
the plugin list with a toggle like any other. Reload the window afterwards
(`Developer: Reload Window`).

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

```bash
git clone --branch v1.0.0 https://github.com/TOMOSIA-VIETNAM/open-pr ~/open-pr
agy plugin install ~/open-pr
```

Skills become slash commands in the TUI: `/open-pr-review` and the other three.

## Local install

For Cursor, Codex, Gemini CLI and Antigravity, when the catalog route is not available to you:

```bash
git clone --branch v1.0.0 https://github.com/TOMOSIA-VIETNAM/open-pr ~/open-pr
~/open-pr/scripts/install-local.sh
```

Clone a release tag rather than the default branch, so you get a version that was cut deliberately.
Read the script before you run it — it is in the repository you just cloned, for exactly that reason.
Nothing here pipes a download into a shell.

By default it installs the four skills into `~/.agents/skills/`, which Codex and Gemini CLI both read,
so one run covers both. The other two platforms have a place of their own:

```bash
~/open-pr/scripts/install-local.sh --platform cursor        # the whole plugin, in Cursor's local plugin dir
~/open-pr/scripts/install-local.sh --platform antigravity   # skills, in ~/.gemini/antigravity-cli/skills
```

Other flags: `--target DIR` to install anywhere else, `--copy` if your platform will not follow
symlinks, `--uninstall` to remove what it installed.

What lands is a symlink back into the clone, so updating every platform at once is:

```bash
git -C ~/open-pr pull
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
