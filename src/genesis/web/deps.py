"""Dependency injection — service singleton and template access."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from fastapi import Request

from genesis.persistence.event_log import EventLog
from genesis.policy.resolver import PolicyResolver
from genesis.service import GenesisService


@lru_cache()
def get_resolver() -> PolicyResolver:
    config_dir = Path(__file__).parent.parent.parent.parent / "config"
    return PolicyResolver.from_config_dir(config_dir)


@lru_cache()
def get_service() -> GenesisService:
    resolver = get_resolver()

    # Keep web tests deterministic and isolated from disk state.
    if "PYTEST_CURRENT_TEST" in os.environ or "PYTEST_VERSION" in os.environ:
        return GenesisService(resolver, event_log=EventLog())

    # Web runtime uses durable event storage so audit evidence survives restarts.
    data_dir = Path(__file__).resolve().parents[3] / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return GenesisService(
        resolver,
        event_log=EventLog(storage_path=data_dir / "events.web.jsonl"),
    )


def get_templates(request: Request):
    return request.app.state.templates
