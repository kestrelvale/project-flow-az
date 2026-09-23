#!/usr/bin/env python3
"""project-flow 端到端验收（ATDD）：熔断 → 阻塞 → 交接 → 核销 → 门禁 → 交付 全链路。

与单元测试的分工：这里只跑真实 CLI + 真实文件状态迁移，断言用户可观察的行为。
"""
from __future__ import annotations

import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

PF = Path.home() / ".codex/skills/project-flow-az"
BUDGET, BOOT, GATE, DELIVER = (PF/"scripts"/n for n in ("flow-budget.py","flow-boot.py","flow-gate.py","flow-deliver.py"))
UID = "01a0c6f8-324a-7112-82de-d0f97e2f21d4"
FOREIGN = "deadbeef-0000-4000-8000-000000000000"
results: list[tuple[bool, str]] = []

def check(ok: bool, label: str, extra: str = "") -> None:
    results.append((ok, label))
    print(("  PASS  " if ok else "  FAIL  ") + label + ("" if ok else f" :: {extra[:400]}"))

def run(*args, cwd=None):
    return subprocess.run([sys.executable, *map(str, args)], text=True, capture_output=True, cwd=cwd)

def make_project(root: Path, ledger: str | None) -> Path:
    flow = root/"flow"
    for d in ("tasks","history","trash","规范","budget","specs"): (flow/d).mkdir(parents=True, exist_ok=True)
    (flow/"规范"/"VERSION").write_text((PF/"VERSION").read_text(), encoding="utf-8")
    (flow/"plan.md").write_text("# Plan\n## 当前聚焦待办 (P0)\n- [ ] T1 [验收] 端到端验收\n", encoding="utf-8")
    for n in ("charter.md","decisions.md","踩坑记录.md"): (flow/n).write_text("", encoding="utf-8")
    (flow/"进展.md").write_text("## 2026-09-22 · 旧交接棒 · T1\n- 现状: 旧\n", encoding="utf-8")
    (flow/"tasks"/"T1.md").write_text("\n".join([
        "ticket_id: T1","schema: v2","objective: 端到端验收","mode: execute","method: SDD,TDD,ATDD,BDD",
        "scope: 输入=x；输出=y；边界=z","write_whitelist: tests/x.py","red_test: tests/test_x.py",
        "verify_command: python3 tests/test_x.py","acceptance: Given A，When B，Then C","evidence: ev.txt",
        "next_agent: Codex Plan Mode","next_action: 开工","spec_ledger: flow/specs/T1.md",
    ]), encoding="utf-8")
    if ledger is not None: (flow/"specs"/"T1.md").write_text(ledger, encoding="utf-8")
    return flow

def write_session(path: Path, turns: int, input_tokens: int = 40_000) -> None:
    stem = path.stem   # 唯一 id：真实 rollout 的 turn/call id 全局唯一
    with path.open("w", encoding="utf-8") as h:
        for i in range(turns):
            h.write(json.dumps({"type":"event_msg","payload":{"type":"task_started","turn_id":f"{stem}-turn-{i}","model_context_window":950_000}}, ensure_ascii=False)+"\n")
        h.write(json.dumps({"type":"token_usage_record","payload":{"usage":{"input_tokens":input_tokens,"cached_input_tokens":0},"turn_token_usage":{"input_tokens":input_tokens,"output_tokens":10},"thread_token_usage":{"input_tokens":input_tokens},"session_file":str(path)}}, ensure_ascii=False)+"\n")
        for i in range(turns):
            h.write(json.dumps({"type":"response_item","payload":{"type":"function_call","name":"exec_command","call_id":f"c{i}"}}, ensure_ascii=False)+"\n")

def main() -> int:
    tmp = Path(tempfile.mkdtemp()); root = tmp/"proj"
    flow = make_project(root, "- [ ] SPE-1 | 登录四态 | 证据：\n- [x] SPE-2 | 旧项 | 证据：pytest exit 0\n")
    (root/"tests").mkdir(); (root/"tests"/"test_x.py").write_text("assert True\n", encoding="utf-8"); (root/"ev.txt").write_text("Exit 0\n", encoding="utf-8")
    sessions = tmp/"sessions"; sessions.mkdir()

    print("[1] 熔断判定：多 rollout 文件按累计规模聚合")
    write_session(sessions/f"rollout-old-{UID}.jsonl", 20)
    write_session(sessions/f"rollout-new-{UID}.jsonl", 8)
    r = run(BUDGET,"--thread-id",UID,"--sessions-root",sessions,"--project",root,"--read-only","--json")
    rep = json.loads(r.stdout or "{}")
    check(rep.get("level") == "STOP" and rep.get("rounds") == 28, "跨文件聚合判 STOP（去重后轮次 20+8 = 28 ≥ 25）", str(rep.get("level"))+" rounds="+str(rep.get("rounds")))

    print("[2] 提示词必须在回复里出现（回复可见性机检）")
    r = run(BUDGET,"--thread-id",UID,"--sessions-root",sessions,"--project",root,"--read-only")
    check("上轮回复缺失接力提示词" in r.stdout and "project-flow 接力提示词" in r.stdout, "未贴提示词时点名并附整段", r.stdout[-200:])

    print("[4] 取回接力提示词：会话解析不到也要能取（回执兜底）+ --intent 覆盖")
    (flow/"budget"/"20260923-130000-stop.json").write_text(json.dumps({
        "operation":"budget_stop","thread_id":UID,"stopped_at":"2026-09-23T13:00:00",
        "handoff_prompt":"继续执行 project-flow 任务，请先按硬首动运行：\npython3 ~/.codex/skills/project-flow-az/scripts/flow-boot.py . --intent \"旧意图\"\n",
    }, ensure_ascii=False), encoding="utf-8")
    r = run(BUDGET,"--print-relay","--project",root,"--thread-id","00000000-0000-4000-8000-000000000000","--intent","验收用意图")
    check("project-flow 接力提示词" in r.stdout and '--intent "验收用意图"' in r.stdout, "回执兜底取回并覆盖 intent", r.stdout[:160])

    print("[3] 未交接 → 柔性阻塞（handoff-only + 拒绝登记新意图）")
    (flow/"budget"/"20260923-120000-stop.json").write_text(json.dumps({"operation":"budget_stop","thread_id":UID,"input_tokens":300000,"rounds":22,"tool_calls":200,"reasons":["工具调用 200 >= 160"],"handoff_head":"## 2026-09-22 · 旧交接棒 · T1","handoff_prompt":"继续执行 project-flow 任务，请先按硬首动运行：\npython3 ~/.codex/skills/project-flow-az/scripts/flow-boot.py . --intent \"旧意图\"\n\n上一会话已触发预算熔断。\n"},ensure_ascii=False), encoding="utf-8")
    r = run(BOOT,root,"--intent","端到端验收","--skip-budget","--thread-id",UID)
    check("【柔性阻塞】" in r.stdout and "拒绝登记新意图" in r.stdout and "Execute 路由" not in r.stdout, "未交接即降级 handoff-only", r.stdout[:200])

    print("[5] 空洞交接棒 / 外来会话交接棒 都不得核销")
    for label, title, extra in (("空洞","## 2026-09-23 · T1 · 交了", ""), ("外来会话",f"## 2026-09-23 · T1 · 交接棒 · thread={FOREIGN}","")):
        (flow/"进展.md").write_text(title+"\n- 干了点活\n"+(extra or "")+"\n", encoding="utf-8")
        r = run(BOOT,root,"--intent","端到端验收","--skip-budget","--thread-id",UID)
        check("【柔性阻塞】" in r.stdout, f"{label}交接棒不核销", r.stdout[:120])

    print("[6] 当事会话 + SDD 蒸馏交接棒 → 核销、阻塞解除")
    (flow/"进展.md").write_text("\n".join([
        f"## 2026-09-23 · T1 · 交接棒（SDD 蒸馏） · thread={UID}",
        "- 规格点 SPE-1 | 登录四态 | 证据：pytest exit 0","- 现状：已交接","- 还剩：无",
        "- 卡在哪：无","- 下一步：开新会话","", "## 2026-09-22 · 旧交接棒 · T1","- 现状: 旧",
    ])+"\n", encoding="utf-8")
    r = run(BOOT,root,"--intent","端到端验收","--skip-budget","--thread-id",UID)
    check("【柔性阻塞】" not in r.stdout and "Execute 路由" in r.stdout, "核销后恢复 Execute 路由", r.stdout[:160])

    print("[7] 规格点台账门禁")
    (flow/"tasks"/"T1.md").write_text((flow/"tasks"/"T1.md").read_text().replace("mode: execute","mode: review"), encoding="utf-8")
    r = run(GATE,flow/"tasks"/"T1.md","--phase","review")
    check(r.returncode != 0 and "未回收" in r.stdout, "有未回收规格点 → review 门禁拦", r.stdout[-160:])
    (flow/"specs"/"T1.md").write_text("- [x] SPE-1 | 登录四态 | 证据：\n", encoding="utf-8")
    r = run(GATE,flow/"tasks"/"T1.md","--phase","review")
    check(r.returncode != 0 and "假销账" in r.stdout, "假销账 → review 门禁拦", r.stdout[-160:])
    (flow/"specs"/"T1.md").write_text("- [x] SPE-1 | 登录四态 | 证据：pytest exit 0\n", encoding="utf-8")
    r = run(GATE,flow/"tasks"/"T1.md","--phase","review")
    check(r.returncode == 0, "全部回收且有证据 → 放行", r.stdout[-160:])

    print("[8] 交付：附规格点回收段 + 落盘回执/看板；台账不合格拒绝交付")
    r = run(DELIVER,flow/"tasks"/"T1.md","--changed","tests/test_x.py","--evidence","pytest exit 0")
    check(r.returncode == 0 and "规格点回收" in r.stdout and "交付验收卡" in r.stdout, "交付含回收段与验收卡", r.stdout[-200:])
    check(len(list((flow/"deliveries").glob("*.json"))) == 1 and (flow/"看板.md").is_file(), "回执与看板落盘", "")
    (flow/"specs"/"T1.md").write_text("- [x] SPE-1 | x | 证据：\n", encoding="utf-8")
    r = run(DELIVER,flow/"tasks"/"T1.md","--changed","tests/test_x.py","--evidence","exit 0")
    check(r.returncode == 1, "假销账 → 拒绝交付", f"rc={r.returncode}")

    failed = [label for ok, label in results if not ok]
    print(f"\n验收结论：{len(results)-len(failed)}/{len(results)} 项通过")
    if failed:
        print("未通过："); [print("  -", f) for f in failed]
        return 1
    shutil.rmtree(tmp, ignore_errors=True)
    return 0

if __name__ == "__main__":
    print("=== project-flow 端到端验收（ATDD）===")
    raise SystemExit(main())