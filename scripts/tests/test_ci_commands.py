"""Focused tests for CI/local Cargo command and check execution policy."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
import typer
from typer.testing import CliRunner

from qproj_scripts import _common, bevy_lint, build, check, cli, clippy, test


def _set_ci(monkeypatch: pytest.MonkeyPatch, enabled: bool) -> None:
    if enabled:
        monkeypatch.setenv("CI", "true")
    else:
        monkeypatch.delenv("CI", raising=False)


def test_ci_commands_share_cargo_default_target_and_do_not_force_features(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_ci(monkeypatch, True)
    monkeypatch.setattr(bevy_lint._common, "rustc_sysroot", lambda: "/rust")
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


def test_check_forwards_options_consistently_to_both_linters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_ci(monkeypatch, True)
    monkeypatch.setattr(bevy_lint._common, "rustc_sysroot", lambda: "/rust")
    extra = ["--features", "foo,bar", "--no-default-features", "-p", "demo"]

    invocations = check._invocations(extra)

    assert invocations[0].argv == ["cargo", "clippy", *extra]
    assert invocations[1].argv[-len(extra) :] == extra


def test_check_cli_preserves_forwarded_argument_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_ci(monkeypatch, True)
    captured: list[list[str]] = []

    def fake_invocations(extra: list[str]):
        captured.append(extra)
        return [
            check.Invocation(["clippy"], {}),
            check.Invocation(["bevy-lint"], {}),
        ]

    monkeypatch.setattr(check, "_invocations", fake_invocations)
    monkeypatch.setattr(check, "_run_sequential", lambda _invocations: [0, 0])

    result = CliRunner().invoke(
        cli.app,
        ["check", "--features", "foo,bar", "--no-default-features", "-p", "demo"],
    )

    assert result.exit_code == 0
    assert captured == [["--features", "foo,bar", "--no-default-features", "-p", "demo"]]


def test_workflow_json_arguments_reach_check_without_shell_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_ci(monkeypatch, True)
    args = ["--features", "foo,bar", "--no-default-features", "-p", "demo"]
    monkeypatch.setenv(
        "QPROJ_COMMAND_ARGS_JSON",
        '["--features","foo,bar","--no-default-features","-p","demo"]',
    )
    captured: list[list[str]] = []

    def fake_invocations(extra: list[str]):
        captured.append(extra)
        return [
            check.Invocation(["clippy"], {}),
            check.Invocation(["bevy-lint"], {}),
        ]

    monkeypatch.setattr(check, "_invocations", fake_invocations)
    monkeypatch.setattr(check, "_run_sequential", lambda _invocations: [0, 0])

    result = CliRunner().invoke(cli.app, ["check"])

    assert result.exit_code == 0
    assert captured == [args]


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


def test_check_retains_positional_package_shorthand(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_ci(monkeypatch, True)
    monkeypatch.delenv("LOCAL", raising=False)
    monkeypatch.setattr(bevy_lint._common, "rustc_sysroot", lambda: "/rust")

    invocations = check._invocations(["one", "two"])

    expected = ["-p", "one", "-p", "two"]
    assert invocations[0].argv == ["cargo", "clippy", *expected]
    assert invocations[1].argv[-len(expected) :] == expected


def test_local_package_mode_retains_manifest_fan_out(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_ci(monkeypatch, False)
    monkeypatch.setenv("LOCAL", "1")
    monkeypatch.setattr(bevy_lint._common, "rustc_sysroot", lambda: "/rust")

    invocations = check._invocations(["one", "two"])

    assert [invocation.argv[-1] for invocation in invocations] == [
        "--manifest-dir=one",
        "--manifest-dir=one",
        "--manifest-dir=two",
        "--manifest-dir=two",
    ]


def test_ci_check_runs_linters_sequentially(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_ci(monkeypatch, True)
    events: list[str] = []
    invocations = [
        check.Invocation(["first"], {}),
        check.Invocation(["second"], {}),
    ]
    monkeypatch.setattr(check, "_invocations", lambda _extra: invocations)

    def fake_run(argv, **_kwargs):
        events.append(f"run:{argv[0]}")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(check._common, "run", fake_run)
    ctx = cast(typer.Context, SimpleNamespace(args=[]))

    with pytest.raises(typer.Exit) as exit_info:
        check.main(ctx)

    assert exit_info.value.exit_code == 0
    assert events == ["run:first", "run:second"]


def test_local_check_spawns_all_linters_before_waiting(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_ci(monkeypatch, False)
    events: list[str] = []
    invocations = [
        check.Invocation(["first"], {}),
        check.Invocation(["second"], {}),
    ]
    monkeypatch.setattr(check, "_invocations", lambda _extra: invocations)

    class FakeProcess:
        def __init__(self, name: str) -> None:
            self.name = name

        def wait(self) -> int:
            events.append(f"wait:{self.name}")
            return 0

    def fake_spawn(invocation: check.Invocation):
        events.append(f"spawn:{invocation.argv[0]}")
        return FakeProcess(invocation.argv[0])

    monkeypatch.setattr(check, "_spawn", fake_spawn)
    ctx = cast(typer.Context, SimpleNamespace(args=[]))

    with pytest.raises(typer.Exit) as exit_info:
        check.main(ctx)

    assert exit_info.value.exit_code == 0
    assert events == ["spawn:first", "spawn:second", "wait:first", "wait:second"]


def test_nextest_default_selects_workspace() -> None:
    argv, env = test.cmd([])

    assert argv == ["cargo", "nextest", "run", "--workspace"]
    assert env == {"RUSTC_WRAPPER": "sccache"}
