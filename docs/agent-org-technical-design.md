# AgentOrg 组织编排系统 — 技术设计文档

> 模块代号: `AgentOrg`  
> 后端路径: `src/openakita/orgs/`  
> 前端组件: `OrgEditorView.tsx` / `OrgInboxSidebar.tsx`  
> 版本: v1.0  
> 最后更新: 2026-03-05

---

## 1. 设计目标与技术定位

AgentOrg 是 OpenAkita 的多 Agent 组织编排引擎。它在现有"自由派发"多 Agent 模式之上，新增了一种**持久化的、层级化的**编排范式——用户以可视化方式拖拽构建 Agent 组织架构（类似公司职能体系），使多个 Agent 在一个持久运行的组织上下文中自主通信、协作、自检。

核心技术参考：
- **CrewAI** 的角色驱动（role/goal/backstory 三元组）
- **LangGraph** 的有向图状态机（节点 + 边 + 状态流转）
- **黑板架构模式 (Blackboard Pattern)** 的共享知识库
- **Google A2A** 的 Agent 能力发现协议
- **CORPGEN** 的多任务优先级管理

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│  前端 (React + @xyflow/react)                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ OrgEditorView│  │  ChatView    │  │ OrgInboxSidebar  │  │
│  │ (编辑+实况)   │  │ (@org 命令)  │  │ (消息中心+审批)   │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
└─────────┼─────────────────┼───────────────────┼─────────────┘
          │ REST/WS         │ REST              │ REST/SSE
┌─────────┴─────────────────┴───────────────────┴─────────────┐
│  API 层 (FastAPI)                                            │
│  routes/orgs.py — CRUD + 生命周期 + 命令 + 记忆 + 事件 + 审批  │
└─────────┬───────────────────────────────────────────────────┘
          │
┌─────────┴───────────────────────────────────────────────────┐
│  orgs 模块 (17 个子模块)                                      │
│                                                              │
│  OrgRuntime    OrgMessenger     OrgBlackboard                │
│  (生命周期)     (消息路由)        (三级共享记忆)                 │
│                                                              │
│  OrgToolHandler  OrgIdentity    OrgEventStore                │
│  (工具分发)       (身份继承)      (事件溯源)                    │
│                                                              │
│  OrgHeartbeat    OrgNodeScheduler  OrgScaler                 │
│  (心跳/晨会)      (节点定时任务)     (动态扩编)                  │
│                                                              │
│  OrgInbox        OrgNotifier       OrgPolicies               │
│  (收件箱)         (IM 推送)          (制度管理)                  │
│                                                              │
│  OrgReporter     OrgManager                                  │
│  (报告生成)       (CRUD/持久化)                                 │
└─────────────────────────────────────────────────────────────┘
          │
┌─────────┴───────────────────────────────────────────────────┐
│  数据层                                                       │
│  data/orgs/{org_id}/                                         │
│    ├── org.json          # 组织定义                            │
│    ├── state.json        # 运行时状态快照                       │
│    ├── nodes/{nid}/      # 节点身份/MCP/定时任务                 │
│    ├── policies/         # 制度文件 (Markdown)                  │
│    ├── memory/           # 三级记忆 (jsonl)                     │
│    ├── events/           # 不可变事件流 (按天分文件)              │
│    ├── logs/             # 通信日志 + 任务日志                   │
│    └── reports/          # 晨会纪要 + 周报 + 审计日志            │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 核心数据模型

### 3.1 枚举类型

| 枚举 | 值 | 说明 |
|------|------|------|
| `OrgStatus` | dormant / active / running / paused / archived | 组织生命周期状态 |
| `NodeStatus` | idle / busy / waiting / error / offline / frozen | 节点运行状态 |
| `EdgeType` | hierarchy / collaborate / escalate / consult | 连线类型 |
| `MsgType` | task_assign / task_result / report / question / answer / escalate / broadcast / dept_broadcast / feedback / handshake | 组织内消息类型 |
| `MemoryScope` | org / department / node | 记忆作用域 |
| `MemoryType` | fact / decision / rule / progress / lesson / resource | 记忆分类 |
| `ScheduleType` | cron / interval / once | 定时任务类型 |
| `InboxPriority` | info / notice / warning / action / approval / alert | 收件箱消息优先级 |

### 3.2 主要数据类

- **`Organization`**: 组织根对象，包含节点列表、边列表、心跳/晨会/扩编/通知/记忆等全局配置
- **`OrgNode`**: 节点（岗位），携带角色三元组(title/goal/backstory)、层级、部门、身份配置、权限开关、冻结状态
- **`OrgEdge`**: 有向边，定义两个节点间的关系类型、优先级和带宽限制
- **`OrgMessage`**: 节点间消息，携带类型、优先级、线程 ID、TTL 等元数据
- **`OrgMemoryEntry`**: 记忆条目，支持三级作用域 + 重要度 + TTL 过期
- **`NodeSchedule`**: 节点定时任务，支持 cron/interval/once 三种调度模式
- **`InboxMessage`**: 收件箱消息，支持内联审批（approve/reject）

所有数据类使用 Python `@dataclass`，提供 `to_dict()` / `from_dict()` 序列化方法。

### 3.3 状态机

基于 `OrgRuntime._VALID_TRANSITIONS` 的完整状态流转：

```
DORMANT ──start──> ACTIVE <──complete── RUNNING
                     │ ↑                  ↑  │
                     │ └────resume────┐   │  │
                     │                │   │  │
                     ├──task──────────│───┘  │
                     │                │      │
                     ├──pause──> PAUSED <────┘ (pause)
                     │             │
                     │             │ (resume → ACTIVE)
                     │             │
                stop ← ← ← ← ← ← ┘ (stop)
                  ↓
               DORMANT

   ACTIVE/PAUSED ──archive──> ARCHIVED (终态)
```

有效转换汇总：

| 当前状态 | 可达状态 |
|---------|---------|
| DORMANT | ACTIVE |
| ACTIVE | RUNNING, PAUSED, DORMANT, ARCHIVED |
| RUNNING | ACTIVE, PAUSED, DORMANT |
| PAUSED | ACTIVE, DORMANT, ARCHIVED |
| ARCHIVED | —（终态）|

---

## 4. 核心运行时 (OrgRuntime)

### 4.1 节点 Agent 生命周期：按需激活模型

节点不常驻运行，采用 **lazy activation + LRU cache** 策略：

1. **休眠态 (IDLE)**: 仅 org.json 中的数据存在，无 Agent 实例，零资源消耗
2. **激活态 (BUSY)**: 收到消息/任务/心跳/定时触发时，通过 `AgentFactory.create()` 创建实例
3. **完成回收**: 任务完成后 Agent 实例保留在 LRU 缓存中（TTL=600s，上限 10 个）
4. **快速唤醒**: 缓存命中时跳过初始化，直接复用

### 4.2 工具注入机制

每个节点 Agent 被创建时，OrgRuntime 执行三步注入：

1. **工具目录注入**: 将 `ORG_NODE_TOOLS`（26 个 org_* 工具）注入 Agent 的 `tool_catalog`
2. **上下文绑定**: 在 agent 上设置 `_org_context = {org_id, node_id, tool_handler}`
3. **ToolExecutor 拦截**: Monkey-patch 该 Agent 的 `reasoning_engine._tool_executor.execute_tool()`，所有 `org_*` 前缀的工具调用路由到 `OrgToolHandler.handle()`，其余调用走原始路径

这种拦截式设计的优势：
- 每个 Agent 实例有独立的 org_id/node_id 上下文
- 不污染全局 handler registry
- 非组织模式的 Agent 完全不受影响

### 4.3 消息处理机制

当 A 节点发消息给 B 节点：

```
A 调用 org_send_message
  → OrgToolHandler._handle_org_send_message()
    → OrgMessenger.send(msg)
      → 查找 edge，检查带宽限制
      → 放入 B 的 NodeMailbox (PriorityQueue)
      → 记录到 _pending_messages
      → 更新 wait-for graph
      → 调用 B 的 message_handler（异步 create_task）
        → OrgRuntime._on_node_message()
          → _activate_and_run(org, B_node, formatted_prompt)
            → 创建/复用 B 的 Agent → agent.chat()
```

关键设计：
- 消息处理是**异步的** (`asyncio.create_task`)，不阻塞发送方
- 每条消息有优先级排序（PriorityQueue + 序列号防 TypeError）
- 支持带宽限制（每分钟每条边的消息频率上限）
- 支持 TTL 过期（后台任务定时清理）

### 4.4 死锁检测

OrgMessenger 维护 wait-for graph，每 30 秒执行 DFS 环检测：

```python
# 当 A 发消息给 B 时: wait_graph[A].add(B)
# 当 B 回复 A 时: wait_graph[A].discard(B)
# 检测到环时: 通知共同上级仲裁 + 写入 inbox 告警
```

### 4.5 超时控制

- 每个节点的 `timeout_s`（默认 300s）通过 `asyncio.wait_for()` 强制执行
- 每条消息的 TTL（默认 300s），超时未处理自动过期

---

## 5. 三级共享记忆 (OrgBlackboard)

| 层级 | 作用域 | 容量上限 | 读写权限 | 存储路径 |
|------|--------|----------|----------|----------|
| 组织级 | 全员可见 | 200 条 | 全员读写 | `memory/blackboard.jsonl` |
| 部门级 | 部门内共享 | 100 条/部门 | 部门内读写，他人只读 | `memory/departments/{dept}.jsonl` |
| 节点级 | 私有 | 50 条/节点 | 仅本节点 | `memory/nodes/{node_id}.jsonl` |

记忆在节点 Agent 创建时自动注入到 system prompt 中，包含：
- 组织黑板摘要（最近 N 条重要条目）
- 部门记忆摘要
- 节点私有记忆

容量管理策略：超出上限时按 importance 排序淘汰低价值条目。

---

## 6. 四级身份继承 (OrgIdentity)

```
Level 0: 零配置     → 全局 SOUL + 全局 AGENT + AgentProfile.custom_prompt
Level 1: 有 ROLE.md → 全局 SOUL + 全局 AGENT + 节点 ROLE.md
Level 2: +AGENT.md  → 全局 SOUL + 节点 AGENT + 节点 ROLE.md
Level 3: 完全独立   → 节点 SOUL + 节点 AGENT + 节点 ROLE.md
```

**MCP 叠加继承**: `最终 MCP = 全局已启用 + Profile 关联 + 节点额外 - 节点排除`

**Prompt 组装**: OrgIdentity.build_org_context_prompt() 生成完整的组织上下文提示词，包含：身份层 → 角色层 → 组织架构概览 → 直接关系 → 权限 → 制度索引 → 组织工具说明 → 记忆注入

---

## 7. 子系统一览

### 7.1 心跳与晨会 (OrgHeartbeat)

| 机制 | 触发方式 | 执行内容 |
|------|----------|----------|
| 心跳 | 定时器 (`heartbeat_interval_s`) | 收集全员状态 → 注入顶层 Agent → 审视决策 |
| 晨会 | cron 表达式 (工作日 9:00) | 汇总进展 → 顶层 Agent 主持 → 生成纪要 |
| 周报 | Reporter 手动/定时触发 | 汇总事件流统计 → 生成 Markdown 报告 |

级联深度限制: `heartbeat_max_cascade_depth` 防止心跳触发的无限委派链。

### 7.2 节点定时任务 (OrgNodeScheduler)

独立于组织心跳，每个节点可配置自己的定时值守任务：

- 三种调度模式: cron / interval / once
- 智能调频: 连续 5 次无异常 → 自动降频 (x1.5)；发现异常 → 恢复原频 + 5 分钟后复查
- 汇报策略: always / on_issue / never
- 与组织生命周期绑定: 组织停止 → 所有定时任务暂停

### 7.3 动态扩编 (OrgScaler)

| 类型 | 操作 | 审批流程 |
|------|------|----------|
| 克隆 (Clone) | 复制岗位增加人手 | auto / manager / user |
| 招募 (Recruit) | 新增全新岗位 | 必须 user 审批 |
| 裁撤 (Dismiss) | 移除临时节点 | 直接执行（仅 ephemeral） |

防失控: max_nodes 硬上限 + 每心跳周期扩编上限 + 事件审计。

### 7.4 收件箱与通知 (OrgInbox + OrgNotifier)

收件箱聚合所有组织事件，按 6 级优先级排序（info / notice / warning / action / approval / alert），支持内联审批。每个组织有独立收件箱（`/api/orgs/{id}/inbox`），同时提供跨组织全局收件箱（`/api/org-inbox`）。

IM 推送支持飞书/钉钉/企业微信/Telegram 等通道，每条审批消息携带唯一编号 `#A{seq}`，用户可通过自然语言回复审批（如 `#A12 批准`）。

### 7.5 制度管理 (OrgPolicies)

- 两级制度: 组织级 (`policies/`) + 部门级 (`departments/{dept}/`)
- 自动索引: `README.md` 自动维护
- 预置模板: 通信规范 / 任务管理规范 / 扩编制度
- Agent 可通过 `org_propose_policy` 提议新制度

### 7.6 事件溯源 (OrgEventStore)

所有状态变更以不可变事件流记录（按天分文件 `events/{YYYYMMDD}.jsonl`），支持：
- 时间范围 / 类型 / 执行者多维查询
- 审计日志生成（筛选关键事件）
- 统计报告生成（任务完成率、节点活跃度、每日活动趋势）

---

## 8. API 端点概览

```
# 组织 CRUD
GET/POST       /api/orgs
GET/PUT/DELETE /api/orgs/{id}
POST           /api/orgs/{id}/duplicate | archive | export
POST           /api/orgs/{id}/save-as-template
POST           /api/orgs/from-template

# 模板
GET            /api/orgs/templates
GET            /api/orgs/templates/{template_id}

# 生命周期
POST           /api/orgs/{id}/start | stop | pause | resume
GET            /api/orgs/{id}/status              (SSE 实时状态流)

# 命令与广播
POST           /api/orgs/{id}/command
POST           /api/orgs/{id}/broadcast

# 心跳与晨会
POST           /api/orgs/{id}/heartbeat/trigger
POST           /api/orgs/{id}/standup/trigger

# 节点管理
GET            /api/orgs/{id}/nodes/{nid}/status
GET/PUT        /api/orgs/{id}/nodes/{nid}/identity | mcp
POST           /api/orgs/{id}/nodes/{nid}/freeze | unfreeze | offline | online
DELETE         /api/orgs/{id}/nodes/{nid}/dismiss

# 节点定时任务
GET/POST       /api/orgs/{id}/nodes/{nid}/schedules
PUT/DELETE     /api/orgs/{id}/nodes/{nid}/schedules/{sid}
POST           /api/orgs/{id}/nodes/{nid}/schedules/{sid}/trigger

# 动态扩编
POST           /api/orgs/{id}/scale/clone | recruit
GET            /api/orgs/{id}/scaling/requests
POST           /api/orgs/{id}/scaling/{req_id}/approve | reject

# 记忆
GET/POST/DELETE /api/orgs/{id}/memory

# 制度
GET/PUT/DELETE /api/orgs/{id}/policies/{filename}
GET            /api/orgs/{id}/policies
GET            /api/orgs/{id}/policies/search?q=

# 组织级收件箱
GET            /api/orgs/{id}/inbox
POST           /api/orgs/{id}/inbox/{mid}/read | read-all
POST           /api/orgs/{id}/inbox/{mid}/resolve

# 跨组织全局收件箱 (/api/org-inbox)
GET            /api/org-inbox
GET            /api/org-inbox/unread-count
POST           /api/org-inbox/{mid}/read | read-all
POST           /api/org-inbox/{mid}/act

# 事件、日志与报告
GET            /api/orgs/{id}/events | messages | stats
GET            /api/orgs/{id}/events/replay
GET            /api/orgs/{id}/audit-log
GET            /api/orgs/{id}/reports
GET            /api/orgs/{id}/reports/summary
POST           /api/orgs/{id}/reports/generate

# IM 审批回调
POST           /api/orgs/{id}/im-reply
```

---

## 9. 前端架构

### 9.1 编排编辑器 (OrgEditorView)

基于 `@xyflow/react` (React Flow v12)，两种模式：

- **编辑模式**: 拖拽节点、连线、属性面板、制度管理、组织设置
- **实况模式**: 固定布局 + 运行状态动画（脉冲/粒子/通信流）+ 节点详情浮层

### 9.2 ChatView 集成

- 支持 `@org:组织名` / `@org:组织名/节点名` 命令语法
- 组织模式切换器（替代 Agent 选择器）
- 发送时携带 `org_id` + `target_node_id`

### 9.3 消息侧边栏 (OrgInboxSidebar)

全局组件，360px 可折叠侧边栏：
- 6 级优先级视觉区分
- 内联审批操作（批准/拒绝 + 原因）
- 未读徽章 + 紧急消息脉冲

### 9.4 跨平台支持

| 平台 | 弹窗方式 | 特殊适配 |
|------|----------|----------|
| Tauri 桌面 | `WebviewWindow.create()` 新窗口 | 原生窗口 |
| Web 浏览器 | `window.open()` 新标签 | 浮窗模式 |
| 移动端 (Capacitor) | 内嵌视图 | 紧凑布局，底部弹出面板 |

---

## 10. 预置模板

| 模板 ID | 名称 | 节点数 | 部门数 | 配套制度 |
|---------|------|--------|--------|----------|
| startup-company | 创业公司 | 16 | 5 | 通信规范 + 任务管理 + 扩编制度 |
| software-team | 软件工程团队 | 10 | 3 | 代码审查 + 部署流程 |
| content-ops | 内容运营团队 | 7 | 3 | 内容标准 + 品牌规范 |

---

## 11. 安全与容错

- **路径遍历防护**: `org_id` / `node_id` 禁止含 `..` / `/` / `\`
- **权限分层**: 广播仅 level=0；冻结仅对下级；跨级通信受策略控制
- **超时保护**: 节点任务 `timeout_s` + 消息 TTL
- **死锁检测**: wait-for graph 环检测，每 30 秒执行
- **防扩编失控**: max_nodes 硬上限 + 心跳周期扩编上限
- **事件审计**: 所有操作写入不可变事件流
- **重启恢复**: 启动时从 `state.json` 恢复活跃组织，检查中断任务并重置状态

---

## 12. 与现有系统的关系

| 现有模块 | AgentOrg 的复用/集成方式 |
|----------|--------------------------|
| AgentFactory | 创建节点 Agent 实例 |
| ToolCatalog | 动态注入 org_* 工具 |
| ReasoningEngine + ToolExecutor | 拦截 org_* 工具调用 |
| WebSocket (broadcast_event) | 广播组织状态变更事件 |
| IM Channels | OrgNotifier 推送通知 + 解析审批回复 |
| Identity (SOUL/AGENT) | OrgIdentity 四级继承 |
| AgentOrchestrator | 完全独立并存，互不干扰 |

现有自由派发模式（AgentOrchestrator + AgentDashboardView）完整保留，用户可自由选择使用。
