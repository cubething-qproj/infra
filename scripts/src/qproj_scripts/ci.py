"""Run GitHub Actions workflows locally via ``act``.

Boots a local artifact server in the background (idempotent --- ignores
``docker run`` failure if the container already exists) and points act at
it via the ``ACTIONS_RUNTIME_*`` env vars.
"""

from __future__ import annotations

import subprocess

import typer

from qproj_scripts import _common


def main(ctx: typer.Context) -> None:
    """Boot the artifact server (best-effort) and run ``act``."""
    docker_cmd = [
        "docker",
        "run",
        "--name",
        "artifact-server",
        "-d",
        "-p",
        "8080:8080",
        "--add-host",
        "artifacts.docker.internal:host-gateway",
        "-e",
        "AUTH_KEY=foo",
        "ghcr.io/jefuller/artifact-server:latest",
    ]
    _common.echo(docker_cmd)
    subprocess.run(docker_cmd, check=False)  # idempotent: tolerate "already exists"

    act_cmd = [
        "act",
        "-P",
        "ubuntu-24.04=ghcr.io/catthehacker/ubuntu:act-24.04",
        "--env",
        "ACTIONS_RUNTIME_URL=http://artifacts.docker.internal:8080/",
        "--env",
        "ACTIONS_RUNTIME_TOKEN=foo",
        "--env",
        "ACTIONS_CACHE_URL=http://artifacts.docker.internal:8080/",
        "--artifact-server-path",
        ".artifacts",
        *ctx.args,
    ]
    result = _common.run(act_cmd, check=False)
    raise typer.Exit(result.returncode)
