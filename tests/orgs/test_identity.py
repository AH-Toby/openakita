"""Tests for OrgIdentity — prompt building, layered inheritance."""

from __future__ import annotations

from pathlib import Path

import pytest

from openakita.orgs.identity import OrgIdentity, ResolvedIdentity
from openakita.orgs.models import Organization, OrgNode
from .conftest import make_org, make_node


@pytest.fixture()
def identity(org_dir: Path, tmp_path: Path) -> OrgIdentity:
    global_identity = tmp_path / "identity"
    global_identity.mkdir()
    return OrgIdentity(org_dir, global_identity)


class TestResolve:
    def test_returns_resolved_identity(self, identity: OrgIdentity, persisted_org):
        node = persisted_org.nodes[0]
        resolved = identity.resolve(node, persisted_org)
        assert isinstance(resolved, ResolvedIdentity)
        assert resolved.level >= 0
        assert isinstance(resolved.soul, str)
        assert isinstance(resolved.agent, str)
        assert isinstance(resolved.role, str)

    def test_node_with_identity_files(self, identity: OrgIdentity, persisted_org, org_dir: Path):
        node = persisted_org.nodes[0]
        id_dir = org_dir / "nodes" / node.id / "identity"
        id_dir.mkdir(parents=True, exist_ok=True)
        (id_dir / "SOUL.md").write_text("# 灵魂\n我是CEO的灵魂文件", encoding="utf-8")
        (id_dir / "ROLE.md").write_text("# 角色\n首席执行官", encoding="utf-8")

        resolved = identity.resolve(node, persisted_org)
        assert "灵魂" in resolved.soul or "CEO" in resolved.soul
        assert resolved.role != ""

    def test_global_identity_fallback(self, identity: OrgIdentity, persisted_org, tmp_path: Path):
        global_dir = tmp_path / "identity"
        (global_dir / "SOUL.md").write_text("# 全局灵魂\n默认灵魂", encoding="utf-8")

        node = persisted_org.nodes[0]
        resolved = identity.resolve(node, persisted_org)
        assert "默认灵魂" in resolved.soul or resolved.soul != ""


class TestBuildOrgContextPrompt:
    def test_contains_org_info(self, identity: OrgIdentity, persisted_org):
        node = persisted_org.nodes[0]
        resolved = identity.resolve(node, persisted_org)
        prompt = identity.build_org_context_prompt(
            node, persisted_org, resolved,
            blackboard_summary="- 决策: 使用Python",
        )
        assert persisted_org.name in prompt
        assert node.role_title in prompt

    def test_includes_blackboard(self, identity: OrgIdentity, persisted_org):
        node = persisted_org.nodes[0]
        resolved = identity.resolve(node, persisted_org)
        prompt = identity.build_org_context_prompt(
            node, persisted_org, resolved,
            blackboard_summary="- 重要决策: 采用微服务",
        )
        assert "微服务" in prompt

    def test_includes_dept_summary(self, identity: OrgIdentity, persisted_org):
        node = persisted_org.nodes[1]
        resolved = identity.resolve(node, persisted_org)
        prompt = identity.build_org_context_prompt(
            node, persisted_org, resolved,
            dept_summary="- 技术部会议纪要",
        )
        assert "技术部会议纪要" in prompt

    def test_includes_policy_index(self, identity: OrgIdentity, persisted_org):
        node = persisted_org.nodes[0]
        resolved = identity.resolve(node, persisted_org)
        prompt = identity.build_org_context_prompt(
            node, persisted_org, resolved,
            policy_index="- 沟通规范.md\n- 任务管理.md",
        )
        assert "沟通规范" in prompt


class TestMCPConfig:
    def test_resolve_mcp_inherit_mode(self, identity: OrgIdentity, persisted_org, org_dir: Path):
        node = persisted_org.nodes[0]
        config = identity.resolve_mcp_config(node)
        assert isinstance(config, dict)
