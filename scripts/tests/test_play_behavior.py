"""Behavior-locking tests for ``qproj_scripts.play``.

These tests capture the *current* observable shell-out shape of the
``play`` verb so that subsequent refactors are guarded. They never
invoke ``cargo``, ``rsync``, ``patchelf``, ``readelf``, or ``execvp``
for real: every shell-out boundary is monkeypatched.

Two tests (``test_local_default_does_not_pass_minus_A_to_binary`` and
``test_local_with_explicit_minus_A_currently_dropped``) intentionally
encode a present-day bug where local mode silently drops ``-A``. They
are expected to be *inverted*, not deleted, when that bug is fixed.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from qproj_scripts import play

CARGO_TOML = """\
[package]
name = "demo"
version = "0.1.0"
edition = "2024"
"""

VIRTUAL_CARGO_TOML = """\
[workspace]
members = []
"""

FAKE_READELF = """\
 0x0000000000000001 (NEEDED) Shared library: [libstd-abc.so]
 0x0000000000000001 (NEEDED) Shared library: [libbevy_dylib-def.so]
"""


class _ExecvpSentinel(SystemExit):
    pass


def _make_app() -> typer.Typer:
    """Build a Typer app that registers ``play.main`` exactly like ``cli.py``.

    A second dummy command is registered so Typer does NOT collapse into
    its single-command convenience mode (which would otherwise consume
    the literal subcommand name as a positional ``ctx.args`` entry).
    """
    app = typer.Typer()
    app.command(
        name="play",
        context_settings={
            "allow_extra_args": True,
            "ignore_unknown_options": True,
            "help_option_names": ["-h", "--help"],
        },
    )(play.main)

    @app.command(name="_noop")
    def _noop() -> None:  # pragma: no cover - never invoked
        pass

    return app


def _setup_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, virtual: bool = False) -> Path:
    """Lay down a minimal crate at ``tmp_path`` and chdir into it."""
    (tmp_path / "Cargo.toml").write_text(VIRTUAL_CARGO_TOML if virtual else CARGO_TOML)
    (tmp_path / "assets").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _install_mocks(
    monkeypatch: pytest.MonkeyPatch,
    *,
    tmp_path: Path,
) -> dict[str, list]:
    """Stub every shell-out boundary in ``play`` and return a capture dict."""
    captured: dict[str, list] = {
        "runs": [],  # list[tuple[list[str], dict | None]] from _common.run
        "execvp": [],  # list[tuple[str, list[str], dict[str, str]]] -- argv0, argv, env snapshot
    }

    def fake_build_cmd(extra: list[str]) -> tuple[list[str], dict[str, str]]:
        return (["cargo", "build", *extra], {"BUILD_ENV": "1"})

    def fake_common_run(cmd, *, env_overrides=None, **_kwargs):
        captured["runs"].append((list(cmd), env_overrides))
        return None

    def fake_execvp(argv0, argv):
        # Snapshot LD_LIBRARY_PATH at the moment of exec, since play.py mutates
        # os.environ directly right before the call.
        import os as _os

        env_snapshot = {
            "LD_LIBRARY_PATH": _os.environ.get("LD_LIBRARY_PATH", ""),
        }
        captured["execvp"].append((argv0, list(argv), env_snapshot))
        raise _ExecvpSentinel(0)

    class _ReadelfResult:
        stdout = FAKE_READELF

    def fake_subprocess_run(*_args, **_kwargs):
        return _ReadelfResult()

    # Fake rustc sysroot with a libstd-abc.so under lib/ so rglob succeeds.
    sysroot = tmp_path / "fake-sysroot"
    (sysroot / "lib").mkdir(parents=True)
    (sysroot / "lib" / "libstd-abc.so").write_bytes(b"")

    monkeypatch.setattr(play.build, "cmd", fake_build_cmd)
    monkeypatch.setattr(play._common, "run", fake_common_run)
    monkeypatch.setattr(play._common, "rustc_sysroot", lambda: str(sysroot))
    monkeypatch.setattr(play.os, "execvp", fake_execvp)
    monkeypatch.setattr(play.subprocess, "run", fake_subprocess_run)

    return captured


def _invoke(app: typer.Typer, args: list[str]):
    runner = CliRunner()
    return runner.invoke(app, ["play", *args], catch_exceptions=True)


def _exec_argv0(captured: dict[str, list]) -> str:
    assert captured["execvp"], "expected os.execvp to be invoked"
    return captured["execvp"][0][0]


# ---------------------------------------------------------------------------
# Local-mode tests
# ---------------------------------------------------------------------------


def test_local_default_invokes_build_then_execs_target_debug_package_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup_cwd(tmp_path, monkeypatch)
    monkeypatch.delenv("SSH_CLIENT", raising=False)
    captured = _install_mocks(monkeypatch, tmp_path=tmp_path)

    app = _make_app()
    _invoke(app, [])

    # Build invocation went through with the default `-F dylib` build_args.
    assert captured["runs"], "expected at least one _common.run (the build)"
    build_argv, build_env = captured["runs"][0]
    assert build_argv[:2] == ["cargo", "build"]
    assert "-F" in build_argv and "dylib" in build_argv
    assert build_env == {"BUILD_ENV": "1"}

    # execvp targets ./target/debug/demo (normalized).
    assert Path(_exec_argv0(captured)) == Path("target/debug/demo")


def test_local_default_does_not_pass_minus_A_to_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # NOTE: documents *current* (buggy) behavior of the local path silently
    # dropping the assets override. This test is expected to be UPDATED (not
    # deleted) when the local path is taught to forward -A / BEVY_ASSET_ROOT.
    _setup_cwd(tmp_path, monkeypatch)
    monkeypatch.delenv("SSH_CLIENT", raising=False)
    monkeypatch.delenv("BEVY_ASSET_ROOT", raising=False)
    captured = _install_mocks(monkeypatch, tmp_path=tmp_path)

    _invoke(_make_app(), [])

    _, argv, env_snapshot = captured["execvp"][0]
    assert "-A" not in argv
    # BEVY_ASSET_ROOT was never set into the env on the way to execvp.
    import os as _os

    assert "BEVY_ASSET_ROOT" not in _os.environ
    assert "BEVY_ASSET_ROOT" not in env_snapshot


def test_local_with_explicit_minus_A_currently_dropped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # NOTE: locks current bug -- `-A` on the CLI in local mode is silently
    # dropped. Will be inverted when the local path forwards assets.
    _setup_cwd(tmp_path, monkeypatch)
    monkeypatch.delenv("SSH_CLIENT", raising=False)
    monkeypatch.delenv("BEVY_ASSET_ROOT", raising=False)
    captured = _install_mocks(monkeypatch, tmp_path=tmp_path)

    _invoke(_make_app(), ["-A", "/tmp/whatever"])

    _, argv, env_snapshot = captured["execvp"][0]
    assert "-A" not in argv
    import os as _os

    assert "BEVY_ASSET_ROOT" not in _os.environ
    assert "BEVY_ASSET_ROOT" not in env_snapshot


def test_local_with_package_flag_uses_target_debug_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup_cwd(tmp_path, monkeypatch)
    monkeypatch.delenv("SSH_CLIENT", raising=False)
    captured = _install_mocks(monkeypatch, tmp_path=tmp_path)

    _invoke(_make_app(), ["-p", "foo"])

    assert Path(_exec_argv0(captured)) == Path("target/debug/foo")


def test_local_with_example_flag_uses_examples_subdir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup_cwd(tmp_path, monkeypatch)
    monkeypatch.delenv("SSH_CLIENT", raising=False)
    captured = _install_mocks(monkeypatch, tmp_path=tmp_path)

    _invoke(_make_app(), ["-x", "mygame"])

    assert Path(_exec_argv0(captured)) == Path("target/debug/examples/mygame")


def test_local_with_positional_binary_path_overrides_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup_cwd(tmp_path, monkeypatch)
    monkeypatch.delenv("SSH_CLIENT", raising=False)
    captured = _install_mocks(monkeypatch, tmp_path=tmp_path)

    _invoke(_make_app(), ["custom/bin/path"])

    assert Path(_exec_argv0(captured)) == Path("custom/bin/path")


def test_local_ld_library_path_includes_target_debug_deps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup_cwd(tmp_path, monkeypatch)
    monkeypatch.delenv("SSH_CLIENT", raising=False)
    monkeypatch.delenv("LD_LIBRARY_PATH", raising=False)
    captured = _install_mocks(monkeypatch, tmp_path=tmp_path)

    _invoke(_make_app(), [])

    _, _, env_snapshot = captured["execvp"][0]
    ld = env_snapshot["LD_LIBRARY_PATH"]
    first = ld.split(":")[0]
    assert Path(first) == tmp_path / "target" / "debug" / "deps"


# ---------------------------------------------------------------------------
# Remote-mode (SSH + PSYNC_SERVER_IP) tests
# ---------------------------------------------------------------------------


def _remote_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SSH_CLIENT", "1.2.3.4 22 5678")
    monkeypatch.setenv("PSYNC_SERVER_IP", "10.0.0.5")


def test_remote_mode_runs_patchelf_and_rsync_and_psync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup_cwd(tmp_path, monkeypatch)
    _remote_env(monkeypatch)
    captured = _install_mocks(monkeypatch, tmp_path=tmp_path)

    _invoke(_make_app(), [])

    # First run is the build; subsequent runs are patchelf*/rsync/psync.
    argvs = [argv for argv, _env in captured["runs"]]
    # Drop the build call.
    assert argvs[0][:2] == ["cargo", "build"]
    rest = argvs[1:]

    # Find the operations in order.
    def _idx(predicate) -> int:
        for i, a in enumerate(rest):
            if predicate(a):
                return i
        raise AssertionError(f"no matching call in {rest!r}")

    i_interp = _idx(lambda a: a[:2] == ["patchelf", "--set-interpreter"])
    i_rpath = _idx(lambda a: a[:2] == ["patchelf", "--set-rpath"])
    i_rsync = _idx(lambda a: a[0] == "rsync" and any("10.0.0.5:/home/psync/lib" in p for p in a))
    i_psync = _idx(
        lambda a: (
            a[:2] == ["uvx", "--from"]
            and "cubething_psync" in a
            and "psync" in a
            and any(Path(p) == Path("./target/debug/demo") for p in a)
        )
    )

    assert i_interp < i_rpath < i_rsync < i_psync


def test_remote_mode_forwards_minus_A_to_psync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup_cwd(tmp_path, monkeypatch)
    _remote_env(monkeypatch)
    captured = _install_mocks(monkeypatch, tmp_path=tmp_path)

    _invoke(_make_app(), ["-A", "/assets/dir"])

    psync_calls = [
        argv for argv, _env in captured["runs"] if argv[:2] == ["uvx", "--from"] and "psync" in argv
    ]
    assert psync_calls, "expected a psync invocation"
    argv = psync_calls[-1]
    # -A and /assets/dir must appear adjacent.
    found_pair = any(argv[i] == "-A" and argv[i + 1] == "/assets/dir" for i in range(len(argv) - 1))
    assert found_pair, f"expected ['-A', '/assets/dir'] adjacent in {argv!r}"


# ---------------------------------------------------------------------------
# Virtual-workspace error handling
# ---------------------------------------------------------------------------


def test_default_package_name_raises_typer_bad_parameter_in_virtual_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup_cwd(tmp_path, monkeypatch, virtual=True)
    monkeypatch.delenv("SSH_CLIENT", raising=False)
    _install_mocks(monkeypatch, tmp_path=tmp_path)

    result = _invoke(_make_app(), [])

    assert result.exit_code != 0
    # The typer.BadParameter message should mention [package].name.
    combined = (result.output or "") + ("" if result.exception is None else str(result.exception))
    assert "[package].name" in combined or "package" in combined.lower()
