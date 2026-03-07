"""Tests for OrgRuntime — lifecycle, agent creation, task execution (mocked)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openakita.orgs.manager import OrgManager
from openakita.orgs.runtime import OrgRuntime
from openakita.orgs.models import NodeStatus, OrgStatus
from .conftest import make_org


@pytest.fixture()
def runtime(org_manager: OrgManager) -> OrgRuntime:
    return OrgRuntime(org_manager)


class TestLifecycle:
    async def test_start_and_shutdown(self, runtime: OrgRuntime):
        with patch("openakita.orgs.templates.ensure_builtin_templates"):
            await runtime.start()
        assert runtime._started is True
        await runtime.shutdown()
        assert runtime._started is False

    async def test_start_org(self, runtime: OrgRuntime, org_manager: OrgManager):
        with patch("openakita.orgs.templates.ensure_builtin_templates"):
            await runtime.start()
        try:
            org = org_manager.create(make_org(name="运行测试").to_dict())
            result = await runtime.start_org(org.id)
            assert result is not None

            org_manager.invalidate_cache(org.id)
            loaded = org_manager.get(org.id)
            assert loaded.status in (OrgStatus.ACTIVE, OrgStatus.RUNNING)
        finally:
            await runtime.shutdown()

    async def test_stop_org(self, runtime: OrgRuntime, org_manager: OrgManager):
        with patch("openakita.orgs.templates.ensure_builtin_templates"):
            await runtime.start()
        try:
            org = org_manager.create(make_org(name="停止测试").to_dict())
            await runtime.start_org(org.id)
            await runtime.stop_org(org.id)

            org_manager.invalidate_cache(org.id)
            loaded = org_manager.get(org.id)
            assert loaded.status == OrgStatus.DORMANT
        finally:
            await runtime.shutdown()


class TestGetAccessors:
    async def test_get_org(self, runtime: OrgRuntime, org_manager: OrgManager):
        with patch("openakita.orgs.templates.ensure_builtin_templates"):
            await runtime.start()
        try:
            org = org_manager.create(make_org(name="测试").to_dict())
            await runtime.start_org(org.id)
            got = runtime.get_org(org.id)
            assert got is not None
            assert got.name == "测试"
        finally:
            await runtime.shutdown()

    async def test_get_blackboard(self, runtime: OrgRuntime, org_manager: OrgManager):
        with patch("openakita.orgs.templates.ensure_builtin_templates"):
            await runtime.start()
        try:
            org = org_manager.create(make_org().to_dict())
            await runtime.start_org(org.id)
            bb = runtime.get_blackboard(org.id)
            assert bb is not None
        finally:
            await runtime.shutdown()

    async def test_get_event_store(self, runtime: OrgRuntime, org_manager: OrgManager):
        with patch("openakita.orgs.templates.ensure_builtin_templates"):
            await runtime.start()
        try:
            org = org_manager.create(make_org().to_dict())
            await runtime.start_org(org.id)
            es = runtime.get_event_store(org.id)
            assert es is not None
        finally:
            await runtime.shutdown()

    async def test_get_messenger(self, runtime: OrgRuntime, org_manager: OrgManager):
        with patch("openakita.orgs.templates.ensure_builtin_templates"):
            await runtime.start()
        try:
            org = org_manager.create(make_org().to_dict())
            await runtime.start_org(org.id)
            messenger = runtime.get_messenger(org.id)
            assert messenger is not None
        finally:
            await runtime.shutdown()

    async def test_get_inbox(self, runtime: OrgRuntime, org_manager: OrgManager):
        with patch("openakita.orgs.templates.ensure_builtin_templates"):
            await runtime.start()
        try:
            org = org_manager.create(make_org().to_dict())
            await runtime.start_org(org.id)
            inbox = runtime.get_inbox(org.id)
            assert inbox is not None
        finally:
            await runtime.shutdown()

    def test_get_scaler(self, runtime: OrgRuntime):
        scaler = runtime.get_scaler()
        assert scaler is not None

    def test_get_heartbeat(self, runtime: OrgRuntime):
        hb = runtime.get_heartbeat()
        assert hb is not None

    def test_get_scheduler(self, runtime: OrgRuntime):
        sched = runtime.get_scheduler()
        assert sched is not None

    def test_get_notifier(self, runtime: OrgRuntime):
        notifier = runtime.get_notifier()
        assert notifier is not None

    def test_get_reporter(self, runtime: OrgRuntime):
        reporter = runtime.get_reporter()
        assert reporter is not None

    async def test_get_policies(self, runtime: OrgRuntime, org_manager: OrgManager):
        with patch("openakita.orgs.templates.ensure_builtin_templates"):
            await runtime.start()
        try:
            org = org_manager.create(make_org().to_dict())
            await runtime.start_org(org.id)
            policies = runtime.get_policies(org.id)
            assert policies is not None
        finally:
            await runtime.shutdown()


class TestSendCommand:
    async def test_send_command_to_root(
        self, runtime: OrgRuntime, org_manager: OrgManager,
    ):
        with patch("openakita.orgs.templates.ensure_builtin_templates"):
            await runtime.start()
        try:
            org = org_manager.create(make_org(name="命令测试").to_dict())
            await runtime.start_org(org.id)

            mock_agent = AsyncMock()
            mock_agent.chat = AsyncMock(return_value="收到命令")

            with patch.object(runtime, "_get_or_create_agent", new_callable=AsyncMock, return_value=mock_agent):
                with patch.object(runtime, "_broadcast_ws", new_callable=AsyncMock):
                    result = await runtime.send_command(org.id, None, "做个计划")

            assert result is not None
        finally:
            await runtime.shutdown()


class TestStateTransitions:
    async def test_pause_and_resume(self, runtime: OrgRuntime, org_manager: OrgManager):
        with patch("openakita.orgs.templates.ensure_builtin_templates"):
            await runtime.start()
        try:
            org = org_manager.create(make_org().to_dict())
            await runtime.start_org(org.id)
            await runtime.pause_org(org.id)

            org_manager.invalidate_cache(org.id)
            loaded = org_manager.get(org.id)
            assert loaded.status == OrgStatus.PAUSED

            await runtime.resume_org(org.id)
            org_manager.invalidate_cache(org.id)
            loaded = org_manager.get(org.id)
            assert loaded.status in (OrgStatus.ACTIVE, OrgStatus.RUNNING)
        finally:
            await runtime.shutdown()
