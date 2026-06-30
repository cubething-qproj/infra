"""Behavior-locking tests for ``qproj_scripts.play``.

These tests capture the *current* observable shell-out shape of the
``play`` verb so that subsequent refactors are guarded. They never
invoke ``cargo``, ``rsync``, ``patchelf``, ``readelf``, or ``execvpe``
for real: every shell-out boundary is monkeypatched.
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
        "execvpe": [],  # list[tuple[str, list[str], dict[str, str]]]
    }

    def fake_build_cmd(extra: list[str]) -> tuple[list[str], dict[str, str]]:
        return (["cargo", "build", *extra], {"BUILD_ENV": "1"})

    def fake_common_run(cmd, *, env_overrides=None, **_kwargs):
        captured["runs"].append((list(cmd), env_overrides))
        return None

    def fake_execvpe(argv0, argv, env):
        captured["execvpe"].append((argv0, list(argv), dict(env)))
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
    monkeypatch.setattr(play.os, "execvpe", fake_execvpe)
    monkeypatch.setattr(play.subprocess, "run", fake_subprocess_run)

    return captured


def _invoke(app: typer.Typer, args: list[str]):
    runner = CliRunner()
    return runner.invoke(app, ["play", *args], catch_exceptions=True)


def _exec_argv0(captured: dict[str, list]) -> str:
    assert captured["execvpe"], "expected os.execvpe to be invoked"
    return captured["execvpe"][0][0]


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


def test_local_default_does_not_set_bevy_asset_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Local mode with no ``-A`` must leave ``BEVY_ASSET_ROOT`` untouched in
    # the child env -- Bevy's compile-time default wins. ``-A`` is never an
    # argv flag on the binary; we only ever set it via env.
    _setup_cwd(tmp_path, monkeypatch)
    monkeypatch.delenv("SSH_CLIENT", raising=False)
    monkeypatch.delenv("BEVY_ASSET_ROOT", raising=False)
    captured = _install_mocks(monkeypatch, tmp_path=tmp_path)

    _invoke(_make_app(), [])

    _, argv, env = captured["execvpe"][0]
    assert "-A" not in argv
    assert "BEVY_ASSET_ROOT" not in env
    import os as _os

    assert "BEVY_ASSET_ROOT" not in _os.environ


def test_local_with_explicit_minus_A_warns_and_does_not_set_bevy_asset_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # ``-A`` is psync-only. In local mode we must warn and ignore: no
    # ``BEVY_ASSET_ROOT`` in the child env, no ``-A`` on the argv.
    _setup_cwd(tmp_path, monkeypatch)
    monkeypatch.delenv("SSH_CLIENT", raising=False)
    monkeypatch.delenv("BEVY_ASSET_ROOT", raising=False)
    captured = _install_mocks(monkeypatch, tmp_path=tmp_path)

    warnings: list[str] = []
    real_log = play._common.log

    def capturing_log(msg: str, level=None) -> None:
        if level == "warn":
            warnings.append(msg)
        real_log(msg, level=level)

    monkeypatch.setattr(play._common, "log", capturing_log)

    explicit = tmp_path / "some_assets"
    explicit.mkdir()

    _invoke(_make_app(), ["-A", str(explicit)])

    assert captured["execvpe"], "expected os.execvpe to be invoked"
    _, argv, env = captured["execvpe"][0]
    assert "-A" not in argv
    assert "BEVY_ASSET_ROOT" not in env
    assert any("psync-only" in w and "--assets" in w for w in warnings), warnings


def test_local_default_sets_cargo_manifest_dir_to_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Bevy reads CARGO_MANIFEST_DIR at runtime to locate the assets root;
    # ``cargo run`` injects it, our local exec must too.
    _setup_cwd(tmp_path, monkeypatch)
    monkeypatch.delenv("SSH_CLIENT", raising=False)
    monkeypatch.delenv("CARGO_MANIFEST_DIR", raising=False)
    captured = _install_mocks(monkeypatch, tmp_path=tmp_path)

    _invoke(_make_app(), [])

    _, _, env = captured["execvpe"][0]
    assert env["CARGO_MANIFEST_DIR"] == str(tmp_path.resolve())


def test_local_with_env_flag_warns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # ``-e`` is psync-only. Locally we warn and do not apply it.
    _setup_cwd(tmp_path, monkeypatch)
    monkeypatch.delenv("SSH_CLIENT", raising=False)
    monkeypatch.delenv("FOO", raising=False)
    captured = _install_mocks(monkeypatch, tmp_path=tmp_path)

    warnings: list[str] = []
    real_log = play._common.log

    def capturing_log(msg: str, level=None) -> None:
        if level == "warn":
            warnings.append(msg)
        real_log(msg, level=level)

    monkeypatch.setattr(play._common, "log", capturing_log)

    _invoke(_make_app(), ["-e", "FOO=bar"])

    assert captured["execvpe"], "expected os.execvpe to be invoked"
    _, _, env = captured["execvpe"][0]
    assert env.get("FOO") != "bar"
    assert "FOO=bar" not in env
    assert any("psync-only" in w and "--env" in w for w in warnings), warnings


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

    _, _, env_snapshot = captured["execvpe"][0]
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


def test_remote_mode_still_autodetects_assets_when_minus_A_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Remote mode keeps the cwd/assets autodetect, unlike local mode --
    # this asymmetry is deliberate.
    _setup_cwd(tmp_path, monkeypatch)  # lays down cwd/assets
    _remote_env(monkeypatch)
    captured = _install_mocks(monkeypatch, tmp_path=tmp_path)

    _invoke(_make_app(), [])

    psync_calls = [
        argv for argv, _env in captured["runs"] if argv[:2] == ["uvx", "--from"] and "psync" in argv
    ]
    assert psync_calls, "expected a psync invocation"
    argv = psync_calls[-1]
    expected = str((tmp_path / "assets").resolve())
    # The autodetected path is cwd/assets; it may appear as either the
    # resolved absolute path or as ``Path('assets')`` depending on Path
    # stringification. Match either by checking the pair contains a path
    # whose resolved form equals tmp_path/assets.
    pair_idx = next(
        (i for i in range(len(argv) - 1) if argv[i] == "-A"),
        None,
    )
    assert pair_idx is not None, f"expected -A in {argv!r}"
    assert Path(argv[pair_idx + 1]).resolve() == Path(expected)


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
