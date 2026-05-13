"""Unified CLI wrapping the cubething-qproj infra task scripts.

Each task (``build``, ``play``, ``check``, ...) lives in its own submodule
that defines a Typer sub-app. :mod:`qproj_scripts.cli` mounts those sub-apps
under their verb names and is the only public entry point.
"""
