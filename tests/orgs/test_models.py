"""Tests for openakita.orgs.models — dataclasses, enums, serialization."""

from __future__ import annotations

import pytest

from openakita.orgs.models import (
    EdgeType,
    InboxMessage,
    InboxPriority,
    MemoryScope,
    MemoryType,
    MsgType,
    NodeSchedule,
    NodeStatus,
    Organization,
    OrgEdge,
    OrgMemoryEntry,
    OrgMessage,
    OrgNode,
    OrgStatus,
    ScheduleType,
    _new_id,
    _now_iso,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_new_id_with_prefix(self):
        result = _new_id("test_")
        assert result.startswith("test_")
        assert len(result) == len("test_") + 12

    def test_new_id_without_prefix(self):
        result = _new_id()
        assert len(result) == 12

    def test_new_id_uniqueness(self):
        ids = {_new_id() for _ in range(100)}
        assert len(ids) == 100

    def test_now_iso_format(self):
        ts = _now_iso()
        assert "T" in ts
        assert "+" in ts or "Z" in ts or ts.endswith("+00:00")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestEnums:
    def test_org_status_values(self):
        assert set(OrgStatus) == {
            OrgStatus.DORMANT, OrgStatus.ACTIVE, OrgStatus.RUNNING,
            OrgStatus.PAUSED, OrgStatus.ARCHIVED,
        }
        assert OrgStatus("dormant") == OrgStatus.DORMANT

    def test_node_status_values(self):
        assert NodeStatus.FROZEN.value == "frozen"
        assert NodeStatus("busy") == NodeStatus.BUSY

    def test_edge_type_values(self):
        assert EdgeType.HIERARCHY.value == "hierarchy"
        assert len(EdgeType) == 4

    def test_msg_type_all(self):
        assert len(MsgType) == 13
        assert MsgType.TASK_ASSIGN.value == "task_assign"
        assert MsgType.TASK_DELIVERED.value == "task_delivered"
        assert MsgType.TASK_ACCEPTED.value == "task_accepted"
        assert MsgType.TASK_REJECTED.value == "task_rejected"

    def test_memory_scope_and_type(self):
        assert MemoryScope.ORG.value == "org"
        assert MemoryType.LESSON.value == "lesson"

    def test_schedule_type(self):
        assert ScheduleType.CRON.value == "cron"
        assert ScheduleType.INTERVAL.value == "interval"
        assert ScheduleType.ONCE.value == "once"

    def test_inbox_priority_ordering(self):
        vals = [p.value for p in InboxPriority]
        assert "info" in vals
        assert "alert" in vals
        assert "approval" in vals
        assert "warning" in vals


# ---------------------------------------------------------------------------
# OrgNode
# ---------------------------------------------------------------------------


class TestOrgNode:
    def test_default_creation(self):
        node = OrgNode()
        assert node.id.startswith("node_")
        assert node.status == NodeStatus.IDLE
        assert node.can_delegate is True

    def test_to_dict_and_back(self):
        node = OrgNode(
            id="n1", role_title="测试角色", department="技术部",
            status=NodeStatus.BUSY, skills=["python", "docker"],
        )
        d = node.to_dict()
        assert d["status"] == "busy"
        assert d["skills"] == ["python", "docker"]

        restored = OrgNode.from_dict(d)
        assert restored.id == "n1"
        assert restored.status == NodeStatus.BUSY
        assert restored.skills == ["python", "docker"]

    def test_from_dict_ignores_unknown_keys(self):
        d = {"id": "n1", "role_title": "A", "unknown_field": "X"}
        node = OrgNode.from_dict(d)
        assert node.id == "n1"
        assert not hasattr(node, "unknown_field")

    def test_frozen_fields(self):
        node = OrgNode(
            frozen_by="admin", frozen_reason="违规", frozen_at="2025-01-01",
            status=NodeStatus.FROZEN,
        )
        d = node.to_dict()
        assert d["frozen_by"] == "admin"
        assert d["status"] == "frozen"


# ---------------------------------------------------------------------------
# NodeSchedule
# ---------------------------------------------------------------------------


class TestNodeSchedule:
    def test_default(self):
        s = NodeSchedule()
        assert s.id.startswith("sched_")
        assert s.schedule_type == ScheduleType.INTERVAL
        assert s.enabled is True

    def test_roundtrip(self):
        s = NodeSchedule(
            name="检查服务", schedule_type=ScheduleType.CRON,
            cron="*/5 * * * *", prompt="检查服务健康状态",
        )
        d = s.to_dict()
        assert d["schedule_type"] == "cron"
        restored = NodeSchedule.from_dict(d)
        assert restored.cron == "*/5 * * * *"
        assert restored.schedule_type == ScheduleType.CRON


# ---------------------------------------------------------------------------
# OrgEdge
# ---------------------------------------------------------------------------


class TestOrgEdge:
    def test_roundtrip(self):
        e = OrgEdge(source="a", target="b", edge_type=EdgeType.COLLABORATE)
        d = e.to_dict()
        assert d["edge_type"] == "collaborate"
        restored = OrgEdge.from_dict(d)
        assert restored.edge_type == EdgeType.COLLABORATE
        assert restored.bidirectional is True


# ---------------------------------------------------------------------------
# Organization
# ---------------------------------------------------------------------------


class TestOrganization:
    def test_default(self):
        org = Organization()
        assert org.status == OrgStatus.DORMANT
        assert org.nodes == []
        assert org.heartbeat_enabled is False

    def test_full_roundtrip(self):
        org = Organization(
            id="org1", name="公司",
            nodes=[OrgNode(id="n1", role_title="CEO", level=0, department="管理")],
            edges=[OrgEdge(source="n1", target="n2")],
            heartbeat_enabled=True,
            notify_enabled=True,
            notify_channel="slack",
            tags=["startup"],
        )
        d = org.to_dict()
        assert d["status"] == "dormant"
        assert len(d["nodes"]) == 1
        assert d["notify_enabled"] is True

        restored = Organization.from_dict(d)
        assert restored.name == "公司"
        assert len(restored.nodes) == 1
        assert restored.nodes[0].role_title == "CEO"
        assert restored.notify_channel == "slack"
        assert restored.tags == ["startup"]

    def test_get_node(self, sample_org: Organization):
        assert sample_org.get_node("node_ceo") is not None
        assert sample_org.get_node("nonexistent") is None

    def test_get_root_nodes(self, sample_org: Organization):
        roots = sample_org.get_root_nodes()
        assert len(roots) == 1
        assert roots[0].id == "node_ceo"

    def test_get_children(self, sample_org: Organization):
        children = sample_org.get_children("node_ceo")
        assert len(children) == 1
        assert children[0].id == "node_cto"

    def test_get_parent(self, sample_org: Organization):
        parent = sample_org.get_parent("node_cto")
        assert parent is not None
        assert parent.id == "node_ceo"

    def test_get_parent_root(self, sample_org: Organization):
        assert sample_org.get_parent("node_ceo") is None

    def test_get_departments(self, sample_org: Organization):
        depts = sample_org.get_departments()
        assert "技术部" in depts
        assert "管理层" in depts


# ---------------------------------------------------------------------------
# OrgMessage
# ---------------------------------------------------------------------------


class TestOrgMessage:
    def test_roundtrip(self):
        msg = OrgMessage(
            from_node="a", to_node="b",
            msg_type=MsgType.TASK_ASSIGN, content="do X",
        )
        d = msg.to_dict()
        assert d["msg_type"] == "task_assign"
        restored = OrgMessage.from_dict(d)
        assert restored.msg_type == MsgType.TASK_ASSIGN


# ---------------------------------------------------------------------------
# OrgMemoryEntry
# ---------------------------------------------------------------------------


class TestOrgMemoryEntry:
    def test_roundtrip(self):
        entry = OrgMemoryEntry(
            scope=MemoryScope.DEPARTMENT,
            scope_owner="技术部",
            memory_type=MemoryType.DECISION,
            content="使用 Python 3.12",
            tags=["tech"],
        )
        d = entry.to_dict()
        assert d["scope"] == "department"
        assert d["memory_type"] == "decision"
        restored = OrgMemoryEntry.from_dict(d)
        assert restored.tags == ["tech"]
        assert restored.memory_type == MemoryType.DECISION


# ---------------------------------------------------------------------------
# InboxMessage
# ---------------------------------------------------------------------------


class TestInboxMessage:
    def test_roundtrip(self):
        msg = InboxMessage(
            org_id="org1", org_name="测试",
            priority=InboxPriority.APPROVAL,
            title="审批请求", body="请批准",
            requires_approval=True,
            approval_options=["approve", "reject"],
            approval_id="#A1",
        )
        d = msg.to_dict()
        assert d["priority"] == "approval"
        assert d["approval_id"] == "#A1"
        restored = InboxMessage.from_dict(d)
        assert restored.requires_approval is True
        assert restored.priority == InboxPriority.APPROVAL
