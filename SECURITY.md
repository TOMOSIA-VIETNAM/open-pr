# Security Policy

## Supported versions

Only the latest release is supported. Fixes land on `main` and ship in the next release —
there are no backports to older tags.

## Reporting a vulnerability

Report privately through GitHub, not in a public issue: open
[Security → Report a vulnerability](https://github.com/TOMOSIA-VIETNAM/open-pr/security/advisories/new)
on this repository. The report stays visible only to you and the maintainers until an
advisory is published.

Useful in a report: what an attacker gains, the smallest set of steps that reproduces it,
and which command or file it starts from. Please leave working exploit code out of the
first message.

Expect an acknowledgement within 7 days and a decision on a fix within 30. If a report
goes unanswered past that, escalate by opening a public issue that says a private report
is waiting — with no details of the vulnerability in it.

## What is in scope

This plugin is Markdown that instructs an agent, plus one JSON config per reviewed
repository. Reports worth sending are the ones where following the plugin's own
instructions harms the user: prompt text that talks an agent into leaking credentials or
writing outside the repository it was pointed at, a config value that reaches a shell
unescaped, a command that pushes somewhere it was never given, or an install path that
writes outside the directories `scripts/install-local.sh` names.

The agent's own behaviour is not in scope. Neither is a vendor CLI (`gh`, `glab`) or the
review host — report those to their own maintainers.
