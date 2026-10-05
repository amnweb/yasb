"""Tests for core.cloud.snapshot and core.cloud.restore.

    python -m pytest tests/cloud/test_snapshot_restore.py -q

The path-traversal cases are the point of this file. Everything else is round-tripping.
"""

import os
import tempfile
import zipfile
from pathlib import Path

from core.cloud.errors import QuotaExceededError, RestoreError, SnapshotError, UnsafePathError
from core.cloud.restore import (
    create_safety_archive,
    extract_archive,
    prune_safety_archives,
    restore_archive,
    validate_member,
)
from core.cloud.snapshot import (
    UNLIMITED,
    collect_files,
    create_archive,
)


def _tree(root: Path, files: dict[str, bytes]) -> Path:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return root


CONFIG = {
    "config.yaml": b"watch_stylesheet: true\n",
    "styles.css": b".bar { color: red; }\n",
    "assets/icon.png": b"\x89PNG fake",
    "scripts/hello.ps1": b"Write-Host hi",
}


# --- Collection --------------------------------------------------------------------------


def test_collects_everything_including_subdirectories():
    with tempfile.TemporaryDirectory() as raw:
        root = _tree(Path(raw), CONFIG)
        assert [c.relative for c in collect_files(root)] == sorted(CONFIG)


def test_excludes_logs_including_rotated_ones():
    """core/log.py uses RotatingFileHandler(backupCount=5), so yasb.log.1..5 exist."""
    with tempfile.TemporaryDirectory() as raw:
        noise = {
            "yasb.log": b"x",
            "yasb.log.1": b"x",
            "yasb.log.5": b"x",
            "scratch.tmp": b"x",
            "old.bak": b"x",
            "~$doc.yaml": b"x",
        }
        root = _tree(Path(raw), CONFIG | noise)
        assert [c.relative for c in collect_files(root)] == sorted(CONFIG)


def test_excludes_generated_directories():
    with tempfile.TemporaryDirectory() as raw:
        root = _tree(Path(raw), CONFIG | {"__pycache__/x.pyc": b"x", ".git/HEAD": b"ref"})
        assert [c.relative for c in collect_files(root)] == sorted(CONFIG)


def test_a_large_file_counts_toward_the_snapshot_limit():
    """There is no per-file cap. A file too big for the plan fails the whole backup with a
    clear error, instead of being dropped from one that then reports success."""
    with tempfile.TemporaryDirectory() as raw:
        root = _tree(Path(raw) / "config", CONFIG | {"huge.bin": b"x" * 5000})

        included = collect_files(root)
        assert "huge.bin" in [c.relative for c in included], "a large file was silently dropped"

        destination = Path(raw) / "out.zip"
        try:
            create_archive(root, destination, max_total_bytes=1000)
            raise AssertionError("the plan's size limit was not enforced")
        except QuotaExceededError:
            pass
        assert not destination.exists()


def test_quota_is_checked_before_any_compression():
    with tempfile.TemporaryDirectory() as raw:
        root = _tree(Path(raw), CONFIG)
        destination = Path(raw + "-out.zip")

        try:
            create_archive(root, destination, max_total_bytes=10)
        except QuotaExceededError:
            assert not destination.exists(), "the archive was written despite the quota error"
            return
        raise AssertionError("the size limit was not enforced")


def test_unlimited_disables_a_check():
    with tempfile.TemporaryDirectory() as raw:
        root = _tree(Path(raw) / "config", CONFIG)
        destination = Path(raw) / "out.zip"
        assert create_archive(root, destination, max_total_bytes=UNLIMITED).file_count == len(CONFIG)


def test_missing_config_directory_is_reported_clearly():
    with tempfile.TemporaryDirectory() as raw:
        try:
            collect_files(Path(raw) / "nope")
            raise AssertionError("a missing directory was accepted")
        except SnapshotError:
            pass


# --- Archive -----------------------------------------------------------------------------


def test_archive_is_deterministic_for_unchanged_input():
    with tempfile.TemporaryDirectory() as raw:
        # The tree lives in a subdirectory so the archives are not written into it.
        root = _tree(Path(raw) / "config", CONFIG)
        first = create_archive(root, Path(raw) / "a.zip")
        second = create_archive(root, Path(raw) / "b.zip")
        assert first.file_count == second.file_count
        assert (Path(raw) / "a.zip").read_bytes() == (Path(raw) / "b.zip").read_bytes()


def test_archive_entries_use_posix_relative_paths():
    with tempfile.TemporaryDirectory() as raw:
        root = _tree(Path(raw) / "config", CONFIG)
        create_archive(root, Path(raw) / "out.zip")
        with zipfile.ZipFile(Path(raw) / "out.zip") as archive:
            names = archive.namelist()
        assert "assets/icon.png" in names
        assert not any("\\" in name or name.startswith("/") for name in names)


def test_failed_archive_leaves_no_partial_file():
    with tempfile.TemporaryDirectory() as raw:
        root = _tree(Path(raw) / "config", CONFIG)
        destination = Path(raw) / "out.zip"
        try:
            create_archive(root, destination, max_total_bytes=1)
            raise AssertionError("quota was not enforced")
        except QuotaExceededError:
            pass
        assert not destination.exists()
        assert not destination.with_name(destination.name + ".partial").exists()


# --- Path validation: the security-critical part -----------------------------------------

HOSTILE_NAMES = [
    "../escape.yaml",
    "../../escape.yaml",
    "a/../../escape.yaml",
    "/absolute.yaml",
    "//server/share/x.yaml",
    "C:/windows/system32/evil.dll",
    "C:evil.dll",
    "..\\escape.yaml",
    "a\\..\\..\\escape.yaml",
    "notes.txt:hidden",
    "CON",
    "CON.txt",
    "aux.yaml",
    "COM1",
    "LPT9.css",
    "nul",
    "sub/PRN.txt",
    "trailing. /x.yaml",
    "trailing./x.yaml",
    "with\x00null.yaml",
    "..",
    ".",
    "",
]


def test_every_hostile_entry_name_is_rejected():
    accepted = []
    for name in HOSTILE_NAMES:
        try:
            validate_member(name)
        except UnsafePathError:
            continue
        accepted.append(name)
    assert not accepted, f"these hostile names were accepted: {accepted}"


def test_legitimate_entry_names_are_accepted():
    for name in ("config.yaml", "assets/icon.png", "a/b/c/deep.css", "dot.in.name.yaml", "unicode-éàü.yaml"):
        assert validate_member(name).as_posix()


def test_hostile_archive_is_refused_without_touching_the_target():
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        root = _tree(base / "config", {"config.yaml": b"original"})
        outside = base / "escape.yaml"

        hostile = base / "hostile.zip"
        with zipfile.ZipFile(hostile, "w") as archive:
            archive.writestr("config.yaml", "replaced")
            archive.writestr("../escape.yaml", "pwned")

        try:
            restore_archive(hostile, root)
            raise AssertionError("a traversal archive was accepted")
        except UnsafePathError:
            pass

        assert not outside.exists(), "the traversal entry escaped the target directory"
        assert (root / "config.yaml").read_bytes() == b"original", "the target was modified before validation"


# --- Restore -----------------------------------------------------------------------------


def test_round_trip_restores_every_file():
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        root = _tree(base / "config", CONFIG)
        archive = base / "snap.zip"
        create_archive(root, archive)

        target = base / "fresh"  # a brand new machine
        result = restore_archive(archive, target)

        assert sorted(result.restored) == sorted(CONFIG)
        for relative, content in CONFIG.items():
            assert (target / relative).read_bytes() == content


def test_restore_removes_files_the_snapshot_does_not_have():
    """Restoring is a rollback, not a merge. A folder holding half the old state and half
    the new matches neither, and a widget left over from the newer one still loads."""
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        source = _tree(base / "src", CONFIG)
        archive = base / "snap.zip"
        create_archive(source, archive)

        target = _tree(base / "target", {"config.yaml": b"stale", "added-later.txt": b"remove me"})
        result = restore_archive(archive, target)

        assert (target / "config.yaml").read_bytes() == CONFIG["config.yaml"]
        assert not (target / "added-later.txt").exists(), "a file added since the backup survived"
        assert sorted(p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()) == sorted(CONFIG)
        assert result.restored


def test_safety_archive_captures_the_previous_configuration():
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        source = _tree(base / "src", CONFIG)
        archive = base / "snap.zip"
        create_archive(source, archive)

        target = _tree(base / "target", {"config.yaml": b"the original", "yasb.log": b"logs too"})
        safety_dir = base / "safety"
        result = restore_archive(archive, target, safety_dir=safety_dir)

        assert result.safety_archive is not None and result.safety_archive.is_file()
        with zipfile.ZipFile(result.safety_archive) as saved:
            assert saved.read("config.yaml") == b"the original"
            # A safety copy must be complete, including files a backup would skip.
            assert saved.read("yasb.log") == b"logs too"


def test_safety_archives_are_pruned_to_the_newest_five():
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        root = _tree(base / "config", {"config.yaml": b"x"})
        safety_dir = base / "safety"
        safety_dir.mkdir()

        for n in range(8):
            (safety_dir / f"config-2026010{n}-000000.zip").write_bytes(b"PK\x05\x06" + bytes(18))
        prune_safety_archives(safety_dir, keep=5)

        remaining = sorted(p.name for p in safety_dir.glob("config-*.zip"))
        assert len(remaining) == 5
        assert remaining[0] == "config-20260103-000000.zip"  # oldest three dropped
        assert create_safety_archive(root, safety_dir) is not None


def test_safety_archive_is_none_when_there_is_nothing_to_save():
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        assert create_safety_archive(base / "does-not-exist", base / "safety") is None


def test_corrupt_archive_is_refused_and_target_is_untouched():
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        target = _tree(base / "config", {"config.yaml": b"original"})

        for name, content in {
            "not a zip": b"this is not a zip file at all",
            "empty": b"",
            "truncated": b"PK\x03\x04truncated garbage",
        }.items():
            broken = base / "broken.zip"
            broken.write_bytes(content)
            try:
                restore_archive(broken, target)
                raise AssertionError(f"{name} was accepted")
            except RestoreError:
                pass
            assert (target / "config.yaml").read_bytes() == b"original"


def test_missing_archive_is_reported_clearly():
    with tempfile.TemporaryDirectory() as raw:
        try:
            restore_archive(Path(raw) / "nope.zip", Path(raw) / "config")
            raise AssertionError("a missing archive was accepted")
        except RestoreError:
            pass


def test_restore_leaves_no_staging_directory_behind():
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        source = _tree(base / "src", CONFIG)
        archive = base / "snap.zip"
        create_archive(source, archive)

        target = base / "target"
        restore_archive(archive, target)
        leftovers = [p for p in base.iterdir() if p.name.startswith(".target.restore-")]
        assert not leftovers, f"staging directories left behind: {leftovers}"


def test_rollback_restores_the_original_after_a_mid_restore_failure():
    """A crafted archive that passes validation but fails on write must not lose data."""
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        target = _tree(base / "config", {"config.yaml": b"precious original"})
        safety_dir = base / "safety"

        archive = base / "snap.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("config.yaml", "replacement")
            zf.writestr("nested/file.css", "more")

        # Fail the directory swap, which happens after the old config has been removed.
        # That is the worst moment for it: the folder is empty and only the safety archive
        # can put it back.
        original_replace = os.replace

        def failing_replace(src, dst, *args, **kwargs):
            raise OSError(5, "simulated failure")

        os.replace = failing_replace
        try:
            restore_archive(archive, target, safety_dir=safety_dir)
            raise AssertionError("the simulated failure did not propagate")
        except RestoreError:
            pass
        finally:
            os.replace = original_replace

        assert (target / "config.yaml").read_bytes() == b"precious original", "rollback did not restore the original"
        assert not (target / "nested" / "file.css").exists(), "a partially restored file was left behind"


# --- User exclude rules ------------------------------------------------------------------


def test_crash_dumps_are_not_backed_up():
    """The CLI writes dumps into the config directory, so they are generated, not authored."""
    with tempfile.TemporaryDirectory() as raw:
        root = _tree(Path(raw), CONFIG | {"dumps/crash-1.dmp": b"x"})
        assert [c.relative for c in collect_files(root)] == sorted(CONFIG)


def test_a_user_rule_without_a_slash_matches_the_file_name_anywhere():
    with tempfile.TemporaryDirectory() as raw:
        root = _tree(Path(raw), CONFIG | {".env": b"KEY=1", "scripts/deploy.env": b"KEY=2"})
        kept = [c.relative for c in collect_files(root, ("*.env",))]
        assert kept == sorted(CONFIG), "a name-only rule should exclude the file at any depth"


def test_a_user_rule_with_a_slash_matches_the_relative_path():
    """`secrets/*` used to match nothing at all, because only the file name was ever tested."""
    with tempfile.TemporaryDirectory() as raw:
        extra = {"secrets/keys.txt": b"shh", "notes/keys.txt": b"fine"}
        root = _tree(Path(raw), CONFIG | extra)
        kept = [c.relative for c in collect_files(root, ("secrets/*",))]
        assert "secrets/keys.txt" not in kept, "a path rule did not exclude its own directory"
        assert "notes/keys.txt" in kept, "a path rule excluded a file outside it"


def test_a_name_rule_does_not_match_against_the_path():
    """`keys.txt` must not be read as a path fragment, or it would exclude by accident."""
    with tempfile.TemporaryDirectory() as raw:
        root = _tree(Path(raw), CONFIG | {"secrets/keys.txt": b"shh"})
        assert "secrets/keys.txt" not in [c.relative for c in collect_files(root, ("keys.txt",))]


def test_user_rules_are_case_insensitive_like_the_built_ins():
    with tempfile.TemporaryDirectory() as raw:
        root = _tree(Path(raw), CONFIG | {"Secret.ENV": b"x"})
        assert [c.relative for c in collect_files(root, ("*.env",))] == sorted(CONFIG)


def test_no_user_rules_leaves_collection_unchanged():
    with tempfile.TemporaryDirectory() as raw:
        root = _tree(Path(raw), CONFIG)
        assert collect_files(root, ()) == collect_files(root)


def test_create_archive_honours_user_rules():
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        root = _tree(base / "config", CONFIG | {"secrets/keys.txt": b"shh"})
        blob = base / "snap.zip"
        create_archive(root, blob, exclude=("secrets/*",))
        with zipfile.ZipFile(blob) as archive:
            assert "secrets/keys.txt" not in archive.namelist(), "an excluded file reached the archive"


def test_a_directory_rule_does_not_match_files_outside_it():
    """`tools/*` must not read as `*`. It did, which made the settings page warn that every
    directory rule was about to exclude config.yaml."""
    with tempfile.TemporaryDirectory() as raw:
        root = _tree(Path(raw), CONFIG | {"tools/build.ps1": b"x"})
        kept = [c.relative for c in collect_files(root, ("tools/*",))]
        assert "config.yaml" in kept, "a directory rule swallowed a file at the root"
        assert "styles.css" in kept
        assert "tools/build.ps1" not in kept, "the directory rule did not apply to its own files"


def test_config_and_styles_survive_a_rule_that_matches_them():
    """The bar cannot start without these two, so no user rule may drop them."""
    with tempfile.TemporaryDirectory() as raw:
        root = _tree(Path(raw), CONFIG | {"data.yaml": b"x", "theme.css": b"x"})
        kept = [c.relative for c in collect_files(root, ("*.yaml", "*.css"))]
        assert "config.yaml" in kept, "config.yaml was excluded by a user rule"
        assert "styles.css" in kept, "styles.css was excluded by a user rule"
        assert "data.yaml" not in kept, "the rule stopped applying to ordinary files"
        assert "theme.css" not in kept


def test_protection_is_the_root_pair_only():
    """A theme's own config.yaml deeper in the tree is still the user's to exclude."""
    with tempfile.TemporaryDirectory() as raw:
        root = _tree(Path(raw), CONFIG | {"themes/dark/config.yaml": b"x"})
        kept = [c.relative for c in collect_files(root, ("*.yaml",))]
        assert "config.yaml" in kept
        assert "themes/dark/config.yaml" not in kept, "protection leaked to a nested file"


def test_an_explicit_rule_naming_config_still_cannot_exclude_it():
    with tempfile.TemporaryDirectory() as raw:
        root = _tree(Path(raw), CONFIG)
        kept = [c.relative for c in collect_files(root, ("config.yaml", "styles.css"))]
        assert "config.yaml" in kept
        assert "styles.css" in kept


def test_a_failed_rollback_is_reported_not_swallowed():
    """The folder is emptied before the swap, so if the copy will not go back either the
    user is left with nothing and no idea the safety archive exists. That has to reach the
    error they see, because there is no log in a GUI build to find it in."""
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        target = _tree(base / "config", {"config.yaml": b"precious original"})
        safety_dir = base / "safety"

        archive = base / "snap.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("config.yaml", "replacement")

        original_replace = os.replace
        original_extractall = zipfile.ZipFile.extractall

        def failing_replace(src, dst, *args, **kwargs):
            raise OSError(5, "simulated failure")

        def failing_extractall(self, *args, **kwargs):
            raise OSError(5, "the rollback failed too")

        os.replace = failing_replace
        zipfile.ZipFile.extractall = failing_extractall
        try:
            restore_archive(archive, target, safety_dir=safety_dir)
            raise AssertionError("the failure did not propagate")
        except RestoreError as exc:
            message = str(exc)
        finally:
            os.replace = original_replace
            zipfile.ZipFile.extractall = original_extractall

        assert "could not be put back" in message, message
        assert "safety" in message, "the message does not say where the copy is"
        assert list(safety_dir.glob("config-*.zip")), "no safety archive was written"


def test_extract_archive_writes_the_snapshot_into_the_folder():
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        source = _tree(base / "src", CONFIG)
        archive = base / "snap.zip"
        create_archive(source, archive)

        target = base / "saved"
        written = extract_archive(archive, target)

        assert sorted(written) == sorted(CONFIG)
        assert (target / "assets" / "icon.png").read_bytes() == CONFIG["assets/icon.png"]


def test_extract_archive_never_removes_what_is_already_there():
    """The difference from restore_archive, and the reason this exists. Restore replaces the
    directory it is given; this one is pointed at a folder the user chose, so deleting
    anything in it would be destroying their files."""
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        source = _tree(base / "src", CONFIG)
        archive = base / "snap.zip"
        create_archive(source, archive)

        target = _tree(base / "documents", {"tax-return.pdf": b"do not delete me"})
        extract_archive(archive, target)

        assert (target / "tax-return.pdf").read_bytes() == b"do not delete me"
        assert (target / "config.yaml").exists()


def test_extract_archive_still_refuses_hostile_entry_names():
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        target = base / "saved"
        outside = base / "escape.yaml"

        hostile = base / "hostile.zip"
        with zipfile.ZipFile(hostile, "w") as archive:
            archive.writestr("config.yaml", "fine")
            archive.writestr("../escape.yaml", "pwned")

        try:
            extract_archive(hostile, target)
            raise AssertionError("a traversal entry was accepted")
        except UnsafePathError:
            pass
        assert not outside.exists()
