"""Focused tests for CI/local Cargo command and check execution policy."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import typer
from typer.testing import CliRunner

from qproj_scripts import _common, bevy_lint, build, check, cli, clippy, test


@pytest.fixture(autouse=True)
def _isolate_command_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("CI", "LOCAL", "QPROJ_COMMAND_ARGS_JSON"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(_common, "rustc_sysroot", lambda: "/rust")


def _set_ci(monkeypatch: pytest.MonkeyPatch, enabled: bool) -> None:
    if enabled:
        monkeypatch.setenv("CI", "true")
    else:
        monkeypatch.delenv("CI", raising=False)


def test_ci_commands_share_cargo_default_target_and_do_not_force_features(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_ci(monkeypatch, True)
    extra = ["--features", "foo,bar", "--no-default-features", "-p", "demo"]

    build_argv, _ = build.cmd(extra)
    clippy_argv, _ = clippy.cmd(extra)
    bevy_argv, _ = bevy_lint.cmd(extra)
    test_argv, _ = test.cmd(extra)

    assert build_argv == ["cargo", "build", *extra]
    assert clippy_argv == ["cargo", "clippy", *extra]
    assert bevy_argv == [
        "bevy",
        "lint",
        "--config",
        'profile.dev.codegen-backend="llvm"',
        *extra,
    ]
    assert test_argv == ["cargo", "nextest", "run", *extra]
    for argv in (build_argv, clippy_argv, bevy_argv, test_argv):
        assert "--all-features" not in argv
        assert not any(arg.startswith("--target-dir") for arg in argv)


def test_local_linters_keep_isolated_targets_without_forcing_features(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_ci(monkeypatch, False)
    monkeypatch.setattr(bevy_lint._common, "rustc_sysroot", lambda: "/rust")
    monkeypatch.setattr(_common, "organization_dir", lambda: Path("/qproj"))

    clippy_argv, clippy_env = clippy.cmd([])
    bevy_argv, bevy_env = bevy_lint.cmd([])

    assert clippy_argv == ["cargo", "clippy"]
    assert clippy_env == {"CARGO_TARGET_DIR": "/qproj/target/clippy"}
    assert bevy_argv == [
        "bevy",
        "lint",
        "--config",
        'profile.dev.codegen-backend="llvm"',
    ]
    assert bevy_env == {
        "RUSTC_WRAPPER": "",
        "BEVY_LINT_SYSROOT": "/rust",
        "CARGO_TARGET_DIR": "/qproj/target/bevy_lint",
    }
    assert "--all-features" not in clippy_argv
    assert "--all-features" not in bevy_argv


@pytest.mark.parametrize("local", [False, True])
@pytest.mark.parametrize(
    ("cli_args", "workflow_args"),
    [
        (["--features", "foo,bar", "--no-default-features", "-p", "demo"], []),
        ([], ["--config", 'build.rustflags=["--cfg", "two words"]', "-p", "demo"]),
        (["-p", "demo"], ["--features", "foo,bar"]),
        (["one", "two"], []),
    ],
    ids=["cli", "workflow", "combined", "positional"],
)
def test_check_cli_forwards_arguments_unchanged(
    local: bool,
    cli_args: list[str],
    workflow_args: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_ci(monkeypatch, True)
    if local:
        monkeypatch.setenv("LOCAL", "1")
    if workflow_args:
        monkeypatch.setenv("QPROJ_COMMAND_ARGS_JSON", json.dumps(workflow_args))
    captured: list[list[str]] = []

    def fake_run(argv, **_kwargs):
        captured.append(list(argv))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(_common, "run", fake_run)

    result = CliRunner().invoke(cli.app, ["check", *cli_args])

    extra = [*workflow_args, *cli_args]
    assert result.exit_code == 0
    assert captured == [clippy.cmd(extra)[0], bevy_lint.cmd(extra)[0]]


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("build", ["cargo", "build", "--features", "foo,bar", "-p", "demo"]),
        (
            "test",
            ["cargo", "nextest", "run", "--features", "foo,bar", "-p", "demo"],
        ),
    ],
)
def test_workflow_json_arguments_reach_build_and_test(
    command: str,
    expected: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QPROJ_COMMAND_ARGS_JSON", '["--features","foo,bar","-p","demo"]')
    captured: list[list[str]] = []

    def fake_run(argv, **_kwargs):
        captured.append(list(argv))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(_common, "run", fake_run)

    result = CliRunner().invoke(cli.app, [command])

    assert result.exit_code == 0
    assert captured == [expected]


@pytest.mark.parametrize("raw", ["not-json", "{}", '["valid", 7]'])
def test_workflow_argument_input_rejects_invalid_json_arrays(
    raw: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QPROJ_COMMAND_ARGS_JSON", raw)

    with pytest.raises(typer.BadParameter):
        _common.command_args([])


@pytest.mark.parametrize("returncodes", [(0, 0), (1, 0), (0, 2)])
def test_ci_check_runs_linters_sequentially(
    returncodes: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_ci(monkeypatch, True)
    events: list[str] = []

    def fake_run(argv, **_kwargs):
        events.append(f"run:{argv[0]}")
        return SimpleNamespace(returncode=returncodes[len(events) - 1])

    monkeypatch.setattr(_common, "run", fake_run)

    result = CliRunner().invoke(cli.app, ["check"])

    assert result.exit_code == max(returncodes)
    assert events == ["run:cargo", "run:bevy"]


@pytest.mark.parametrize("returncodes", [(0, 0), (1, 0), (0, 2)])
def test_local_check_spawns_all_linters_before_waiting(
    returncodes: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_ci(monkeypatch, False)
    events: list[str] = []
    codes: dict[str, int] = dict(zip(("cargo", "bevy"), returncodes, strict=True))

    class FakeProcess:
        def __init__(self, name: str) -> None:
            self.name = name

        def wait(self) -> int:
            events.append(f"wait:{self.name}")
            return codes[self.name]

    def fake_spawn(invocation: check.Invocation):
        events.append(f"spawn:{invocation.argv[0]}")
        return FakeProcess(invocation.argv[0])

    monkeypatch.setattr(check, "_spawn", fake_spawn)

    result = CliRunner().invoke(cli.app, ["check"])

    assert result.exit_code == max(returncodes)
    assert events == ["spawn:cargo", "spawn:bevy", "wait:cargo", "wait:bevy"]


def test_nextest_default_selects_workspace() -> None:
    argv, env = test.cmd([])

    assert argv == ["cargo", "nextest", "run", "--workspace"]
    assert env == {"RUSTC_WRAPPER": "sccache"}
