"""Focused tests for CI/local Cargo command and check execution policy."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
import typer
from typer.testing import CliRunner

from qproj_scripts import _common, build, cli, test


@pytest.fixture(autouse=True)
def _isolate_command_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("CI", "LOCAL", "QPROJ_COMMAND_ARGS_JSON"):
        monkeypatch.delenv(name, raising=False)


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
    test_argv, _ = test.cmd(extra)

    assert build_argv == ["cargo", "build", *extra]
    assert test_argv == ["cargo", "nextest", "run", *extra]
    for argv in (build_argv, test_argv):
        assert "--all-features" not in argv
        assert not any(arg.startswith("--target-dir") for arg in argv)


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
def test_build_cli_forwards_arguments_unchanged(
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

    result = CliRunner().invoke(cli.app, ["build", *cli_args])

    extra = [*workflow_args, *cli_args]
    assert result.exit_code == 0
    assert captured == [build.cmd(extra)[0]]


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


def test_nextest_default_selects_workspace() -> None:
    argv, env = test.cmd([])

    assert argv == ["cargo", "nextest", "run", "--workspace"]
    assert env == {"RUSTC_WRAPPER": "sccache"}
