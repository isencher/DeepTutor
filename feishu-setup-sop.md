---
title: Feishu 配置实战 SOP
source: https://docs.deeptutor.info/partners/feishu-setup-sop/
---

本文是 [Feishu 通道文档](https://docs.deeptutor.info/partners/feishu/) 的实战补充：把"从零到机器人回复 test"拆成 4 个阶段、18 个可核对步骤，并标出每个阶段最常见的失败点。完成本 SOP 后，你应该能在飞书中向机器人发一条消息并收到回复。

> 全程**不需要公网 IP、webhook URL 或反向代理**——DeepTutor 通过 `lark-oapi` SDK 主动拨出 WebSocket 长连接接收事件。

---

## 阶段 1：飞书开放平台配置

### 1. 登录开放平台

打开 <https://open.feishu.cn/>（国际版用 <https://open.larksuite.com/>），使用企业账号登录。

### 2. 创建企业自建应用

进入 **开发者后台** → **创建企业自建应用**，填写应用名称、描述、图标。

### 3. 复制应用凭证

进入应用详情页 → **凭证与基础信息**，复制以下两项备用：

- **App ID**（形如 `cli_xxxxxxxxxxxxxxxx`）
- **App Secret**

> ⚠️ 这两项是后续 DeepTutor 配置的必填字段，丢失只能在此页重置。

### 4. 添加机器人能力

进入 **应用能力 → 添加应用能力 → 机器人**，给机器人取一个展示名称和头像。

### 5. 配置事件订阅

进入 **事件与回调**：

1. **订阅方式**：切换为 **长连接**（**不要**选 webhook，否则需要公网 IP）
2. **添加事件**：搜索并订阅 `im.message.receive_v1`（接收消息）

> ⚠️ 订阅方式选错是第二常见失败点。选了 webhook 但没有公网 IP，事件永远到不了 DeepTutor。

### 6. 配置权限范围

进入 **权限管理**，授予以下 5 项权限：

| 权限名 | 用途 |
|--------|------|
| `im:message` | 读写消息（基础权限） |
| `im:message.group_at_msg.include_bot:readonly` | 群内 @机器人消息 |
| `im:chat.access_event.bot_p2p_chat:read` | 用户进入机器人会话事件 |
| `im:message.p2p_msg:readonly` | 单聊消息读取 |
| `im:message:send_as_bot` | 以机器人身份发送消息 |

> ⚠️ 如需接收图片/文件/语音，额外加 `im:resource`。

### 7. 发布版本

进入 **版本管理与发布 → 创建版本 → 申请发布**。内部应用走内部发布 + 管理员审批。

> ⚠️ **这是最常见的失败点**：版本未发布时，机器人收不到任何事件。后续任何配置改动（权限、事件订阅）都必须**重新发布版本**才能生效。

### 8. 加密策略（可选，默认不启用）

飞书平台默认**不启用事件加密**。如果你没有显式开启加密，**保持默认即可**——DeepTutor 配置侧的 `encrypt_key` 和 `verification_token` 两个字段**留空**就是正确配置。

> 反向陷阱：若平台未启用加密，但 DeepTutor 配置里填了非空 `encrypt_key`，SDK 会尝试解密明文事件，导致事件被丢弃——机器人无响应。

---

## 阶段 2：DeepTutor 环境准备

### 9. 激活虚拟环境

```powershell
cd d:\.dev\DeepTutor
. .\.venv\Scripts\Activate.ps1
```

### 10. 安装 partners extra

`lark-oapi` 属于 `partners` extra，默认不随主包安装：

```powershell
# 推荐：装完整 partners extra（含钉钉、飞书等所有通道 SDK）
pip install -e ".[partners]"

# 或最小化：只装飞书 SDK
pip install "lark-oapi>=1.5.0,<2.0.0"
```

### 11. 验证 SDK 已安装

```powershell
python -c "import lark_oapi; print('lark_oapi', lark_oapi.__version__)"
```

期望输出：`lark_oapi 1.x.x`。若报 `ModuleNotFoundError`，回到第 10 步重装。

> ⚠️ **这是最常见的前置失败点**：SDK 未装时，DeepTutor 启动日志会出现 `Feishu SDK not installed. Run: pip install lark-oapi`，飞书 channel 的 `start()` 在第一行直接 `return`，WebSocket 长连接根本不会建立——机器人自然无响应。

---

## 阶段 3：DeepTutor Partner 配置

### 12. 进入 Partners 面板

启动 DeepTutor（`switch-data start --env <env>` 或 `deeptutor start`），在 Web UI 进入 **Partners**，创建或选择一个 partner（例如 `weliam`）。

### 13. 启用 Feishu 通道

进入 **Channels → Feishu**，把 **Enabled** 开关打开。

### 14. 填写配置字段

| 字段 | 填写内容 | 备注 |
|------|---------|------|
| **Enabled** | ✅ 打开 | |
| **App Id** | 第 3 步复制的 App ID | 形如 `cli_xxxxxxxx` |
| **App Secret** | 第 3 步复制的 App Secret | 保存后自动掩码为 `***` |
| **Encrypt Key** | **留空** | 仅当飞书平台显式启用了事件加密时才填 |
| **Verification Token** | **留空** | 同上 |
| **Allow From** | 测试期填 `*` | 正式使用时换为 `ou_...` open id 列表 |
| **React Emoji** | `THUMBSUP` | 收到消息后立即给消息加的 emoji 反应 |
| **Group Policy** | `mention` | 群里仅 @机器人才回复；DM 总是回复 |
| **Streaming / Send Progress / Send Tool Hints** | 测试期建议全开 | 调试期可见性强 |

点击 **Save**。

### 15. 启用通道

保存后再次确认 **Enabled** 开关为打开状态。若 partner 已在运行，使用 Channels 面板的 **reload** 按钮热重载；否则直接启动 partner。

---

## 阶段 4：启动与验证

### 16. 启动项目

```powershell
. .\.venv\Scripts\Activate.ps1
switch-data start --env <env>
```

### 17. 核对启动日志

打开 `data/user/logs/deeptutor.jsonl`，按顺序确认以下信号：

| 期望日志 | 含义 | 缺失时的排查方向 |
|---------|------|----------------|
| 不再出现 `Feishu SDK not installed` | lark-oapi 已加载 | 回到第 10 步重装 |
| `Feishu bot started with WebSocket long connection` | 通道已启动 | 检查 `app_id`/`app_secret` |
| `No public IP required - using WebSocket to receive events` | 长连接模式正常 | — |
| 无反复 `Feishu WebSocket error` | 连接稳定 | 5 秒自动重连正常；频繁则查网络/凭证 |

### 18. 发送测试消息

在飞书中：

1. 搜索机器人名称，打开 DM 会话
2. 发送一条**纯文本**消息（如 `test`）
3. 立即观察：
   - ✅ **消息应在 1 秒内获得 React Emoji**（默认 ⭐ THUMBSUP）——确认 inbound 事件链路通
   - ✅ **几秒后机器人回复文本**——确认 outbound API 链路通

若两者都达成，配置成功。

---

## 常见故障速查

| 现象 | 根因 | 处理 |
|------|------|------|
| 日志 `Feishu SDK not installed` | `lark-oapi` 未装 | 第 10 步重装 |
| 启动后无 `bot started` 日志 | `app_id` / `app_secret` 为空或错误 | 第 14 步核对字段 |
| 日志正常但发消息无反应 | 应用版本未发布 / 事件订阅选了 webhook / `im.message.receive_v1` 未订阅 | 第 5、7 步重查 |
| 消息有 emoji 反应但无回复 | 缺 `im:message:send_as_bot` 权限，或权限改动未重新发布版本 | 第 6、7 步重查 |
| 启用加密后事件全失效 | DeepTutor 侧 `encrypt_key` 与平台不一致 | 两边对齐后重启 partner |
| 收到 `Authentication Fails / Insufficient Balance` | LLM API key 失效或欠费 | 在 Web UI **Settings → Models** 检查 |

---

## 后续收尾

测试通过后，建议做两件事：

1. **收紧 Allow From**：从日志复制发送者的 `ou_...` open id，替换 `*`，避免机器人被无关账号触发。
2. **关闭调试开关**：把 `Send Tool Hints` 关掉（除非还需要看工具调用过程）。

完整字段说明与高级用法（流式卡片、富文本格式自适应、消息读取事件等）参见 [Feishu 通道文档](https://docs.deeptutor.info/partners/feishu/)。
