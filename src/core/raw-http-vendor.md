# Conventions for a vendor reached by raw HTTP

Read by the `fetch` group of a vendor that ships no CLI, so every entry of every group is `curl` + `jq`.
That vendor's own `fetch.md` owns what is specific to it — base URL, auth variables, terminology,
pagination shape; everything below holds for all of them and is stated only here.

## `curl` flags

`--fail-with-body` on every call: a non-zero exit on an HTTP error AND the response body, which is the only
place the API states what it rejected. FORBIDDEN: `-f` alone (discards that body), `-v` and `-i` (dump the
request's own `Authorization` header into context). `-D -` IS allowed where a response header is the answer
— it prints no request header.

## The credential

Only the NAME of an env var ever enters context. FORBIDDEN: printing or echoing the variable, asking the
user to paste a token into chat, reading a token out of a file, and putting one in a URL — a URL reaches
the server's access log, the shell history and every proxy in between.

Its variable unset ⇒ STOP before the first call and print which variable to set, what the token needs
permission for, and that the `env` block of `~/.claude/settings.json` sets it for every session. FORBIDDEN:
guessing a credential, or continuing far enough to fail on a 401.

A repository-scoped token has no PERSON behind it, so "Fetch account running the command" cannot name one.
Whatever shape that refusal takes on a given vendor, it is the ANSWER: print `UNKNOWN`, let
`core/finding-markers.md` fall back to the marker, and never retry it as if it were an auth failure.

## A JSON payload

Written to a file with a file-writing tool, sent with `--data @<file>`, or piped straight out of `jq`
with `--data @-` — either way the text never becomes a shell word.
FORBIDDEN: a heredoc, `echo`, `-d '<json>'` with any interpolated text, or any other route through the
running shell — finding and reply text quotes the PR's own diff, i.e. attacker-controlled input, and shell
expansion there corrupts the payload or executes it. A body of nothing but digits and a fixed enum is the
one exception, and says so where it is used.

## Splitting a whole-diff response into per-file chunks

A vendor with no per-file patch endpoint answers with one text blob, and both its patch entry and its size
entry cut that blob at `diff --git` boundaries. `<diff_cmd>` = that vendor's own whole-diff command.

`LC_ALL=C` is MANDATORY on both: `awk`'s `length` counts CHARACTERS, and a UTF-8 locale would size a patch
full of accented or CJK text well under its real byte count.

**Patch, dropping every chunk that reaches the threshold** — `<max_patch_bytes>` = the caller's own
threshold in bytes:

```bash
LC_ALL=C <diff_cmd> | awk -v m=<max_patch_bytes> '/^diff --git /{if(n&&s<m)printf "%s",b; b=""; s=0; n=1}
  n{b=b $0 "\n"; s+=length($0)+1} END{if(n&&s<m)printf "%s",b}'
```

**Bytes per file:**

```bash
LC_ALL=C <diff_cmd> | awk '/^diff --git /{if(n)print s" "p; p=substr($0,index($0," b/")+3); s=0; n=1}
  n{s+=length($0)+1} END{if(n)print s" "p}'
```

A path the vendor's file-list entry returned but this prints nothing for is `UNKNOWN`, NEVER 0: the chunk
is omitted entirely for a binary file and for a diff the server declines to generate, and reading that
absence as 0 bytes would slip the largest file in the PR under every threshold, so it would be neither
reviewed nor reported as skipped.
