## [4.15.4] - 2026-09-23 (外部预算心跳 + 心跳自身两处真 bug 修复)

### Added
- **`flow-heartbeat.py`（外部预算心跳）**：扫描近 N 小时活跃的 project-flow 会话，
  逐个算预算；越过 WARN/STOP 就发 macOS 系统通知 + 追加 `~/.codex/project-flow-heartbeat.log`，
  30 分钟内同会话同等级去重。**能力边界（诚实声明）**：外部进程**不能**往会话里插消息——
  那需要 Codex app 的调度器；本心跳解决的是「该交接了要让你看见」，而不是自动替你交接。
- `assets/templates/com.projectflow.heartbeat.plist` + 已装到
  `~/Library/LaunchAgents/com.projectflow.heartbeat.plist`（StartInterval 900，即每 15 分钟）。
  卸载：`launchctl unload -w ~/Library/LaunchAgents/com.projectflow.heartbeat.plist`。
- `flow-budget.py --read-only`：只读模式，不写熔断回执也不写检查点——外部巡检必须无副作用，
  否则后台任务会往你每个项目的 `flow/budget/` 里灌文件。

### Fixed（心跳自身，均为实测发现的真 bug）
| # | 缺陷 | 证据 | 修法 |
|---|---|---|---|
| 1 | thread_id 解析错误（被时间戳前缀带偏） | 日志出现 `23T01-43-20-` 这种值，预算读数为 `输入 0/0` | 改用 UUID 正则从文件名提取，并加回归测试 |
| 2 | 解析失败被当成告警写入日志 | 日志出现 `[None] ... 输入 0/0 ... 轮次 None` | `level` 不在 {OK,WARN,STOP} 直接跳过，不写日志 |
| 3 | 去重状态被并发实例互相覆盖 | `launchctl kickstart -k` 杀旧实例后，状态表被冲成只剩 1 个键 → 同批会话反复通知 | `save_state` 改读-合并-原子写（tmp + replace），并加回归测试 |

### Verification
- `tests/run-all.sh` 全量 **13 项 Exit 0**（新增 `test-flow-heartbeat.py`）。
- **计划任务实跑验证**：`launchctl kickstart -k` 后，进程由 launchd 自行拉起并写出
  去重状态文件（17:38），日志追加新时间戳；`launchctl list` 显示 `com.projectflow.heartbeat` 已注册、上次退出码 0。
- **只读验证**：心跳运行前后，`~/projects/zhengjie-hrm/flow/budget/guard.json` 的 mtime 不变。

### Docs
- OCR（open-code-review）复用中继端点的结论（2026-09-23 实测，逐条有证据）：**当前不可用**——
  25820（WOYAO 本地代理）429 额度耗尽；Lzh 502「upstream access forbidden」；MiniMax/1mmc 401 密钥无效；
  feichuangtech/fengwind 403；TeamoRouter 余额不足；OpenRouter 该模型已下线；
  25817（Codex 专用）明确返回 `api_key_not_supported`。OCR 配置命令已备好，等一个有额度的 key。

