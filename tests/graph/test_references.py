"""Every path, section and subcommand a file points at must resolve."""

import re

from _common import SRC, text, all_text


def test_plugin_root_refs_exist():
    """Every ${CLAUDE_PLUGIN_ROOT}/<path> the agent is told to Read must exist."""
    missing = []
    for name, body in all_text().items():
        for m in re.finditer(r'CLAUDE_PLUGIN_ROOT\}"?/([A-Za-z0-9_./<>-]+)', body):
            ref = m.group(1)
            if "<" in ref or ref.endswith("/"):
                continue  # resolved at run time (vendor / stack placeholders)
            if not (SRC / ref).exists():
                missing.append((name, ref))
    assert not missing, f"dangling plugin-root refs: {missing}"


def test_backtick_file_refs_exist():
    """A `dir/file.md` mentioned in prose must resolve — catches a moved file."""
    missing = []
    for name, body in all_text().items():
        for m in re.finditer(r"`((?:core|cases|setup|commands|reference)/[a-z-]+\.md)`", body):
            if not (SRC / m.group(1)).exists():
                missing.append((name, m.group(1)))
    assert not missing, f"dangling prose refs: {missing}"


def test_section_refs_resolve():
    """A ref addresses a section either by number (`core/pr-target.md` §2) or by heading
    (`core/repo-settings.md` "Fresh file"); both must land on a heading that exists, so
    renaming one reddens here instead of leaving a dangling ref."""
    bad = []
    for name, body in all_text().items():
        for m in re.finditer(r'`((?:[a-z-]+/)?[a-z-]+\.md)` (?:§(\d)|"([^"]+)")', body):
            target = SRC / m.group(1)
            num, heading = m.group(2), m.group(3)
            wanted = rf"^## {num}\." if num else rf"^## {re.escape(heading)}"
            if not target.exists() or not re.search(wanted, text(target), re.M):
                bad.append((name, m.group(0)))
    assert not bad, f"unresolvable section refs: {bad}"


def test_reference_dir_is_never_read_at_run_time():
    """The schema doc serves a human editor and a migration author. Every number a command
    needs while running — including the build's own config checkpoint — lives in a small atom
    instead, so no run pays for the whole schema to learn one field."""
    for name, body in all_text().items():
        assert "CLAUDE_PLUGIN_ROOT}/reference/" not in body.replace('}"', "}"), name
