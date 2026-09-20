# 运行时合同与接管协议

project-flow 不安装 Hook，也不依赖 Hook。项目级 `.hooks/`、`.claude/settings.json`、`.codex/hooks.json` 不属于本流程控制面。

## 接管入口

模型每轮能看到的只有两类指令：`AGENTS.md` 与 skill 描述。因此运行时合同必须落在 `AGENTS.md`，而不是额外守卫：

- 全局 `~/.codex/AGENTS.md`：跨项目不变的行为准则 + 一句 project-flow 接管条件。
- 项目 `AGENTS.md`：标记块内的四条交付合同（首屏看板 / plan 先落盘 / 验收卡 / 收工进展）。
- Claude 侧对应 `~/.claude/CLAUDE.md` 与项目 `CLAUDE.md`（软链到 `AGENTS.md`）。

接管条件只有一句话：工作根或任一父目录存在 `flow/plan.md`，即进入 project-flow 交付模式，无需用户点名 skill。

## 为什么不用 Hook

Hook 只增加失效点，不解决根本问题：`AGENTS.md` 在会话启动与文件变更时注入，只要合同写进该文件，行为就有保证；写在 Hook 里反而要依赖信任批准、注入协议和版本兼容。

## 收工检查

主控 Agent 在准备结束当前回合前主动检查：任务是否落盘、最小验证是否成功、是否需要在 `flow/进展.md` 顶部写接力记录。未完成或验证失败时不得用文档代替交付。

## 开工入口

执行型回合首动运行 `python3 ~/.codex/skills/project-flow-az/scripts/flow-boot.py . --intent "<本轮任务摘要>"`。该脚本向上定位最近的 `flow/plan.md`，版本落后时热同步，随后审计遗留任务、输出接管路由，并校验本轮意图是否已绑定活跃任务卡。

## 会话接力

复杂任务采用单票独立会话。主控 Agent 根据上下文长度、工具调用数量和任务边界主动换会话；换会话前写入并只读取 `flow/进展.md` 顶部最新记录。

## 定时交付边界

project-flow 不负责在无人交互时启动任务，也不承诺工作时间自动交付。需要定时执行时使用外部 cron、heartbeat 或 automation，并让入口显式读取本文件与 `flow/进展.md`。

## 验证

```bash
bash tests/test-multi-project-structure.sh
python3 -m py_compile scripts/sync-project.py scripts/flow-boot.py scripts/audit-flow.py
```

回归覆盖：模板含四条交付合同、标记块幂等更新、项目自定义内容不被覆盖、无 Hook 残留。
