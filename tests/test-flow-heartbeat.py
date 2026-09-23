#!/usr/bin/env python3
"""心跳监控：thread_id 解析与去重状态合并必须正确（这两处都曾出真 bug）。"""
from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "flow-heartbeat.py"
spec = importlib.util.spec_from_file_location("flow_heartbeat", SCRIPT)
assert spec and spec.loader
hb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hb)


def main() -> None:
    # 1) thread_id 必须从文件名里取 UUID，而不是被时间戳前缀带偏。
    #    实测（2026-09-23）曾得到 `23T01-43-20-` 这种垃圾值，导致预算读数为 0。
    cases = {
        "rollout-2026-09-22T20-30-49-01a0c1cb-b41f-7f73-b5f8-efafcd3d774d_01a0c918-ed4d-79b3-92bd-56b53df6e7d1": "01a0c1cb-b41f-7f73-b5f8-efafcd3d774d",
        "rollout-2026-09-21T10-31-14-01a0c1cd-a264-7321-8779-8440e6de59ac": "01a0c1cd-a264-7321-8779-8440e6de59ac",
        "rollout-无UUID.jsonl": "",
    }
    for stem, expected in cases.items():
        got = hb.thread_id_of(Path(stem + ".jsonl"))
        assert got == expected, (stem, got, expected)

    # 2) 去重状态必须读-合并-写：并发实例各写各的会互相覆盖。
    with tempfile.TemporaryDirectory() as tmp:
        hb.STATE_FILE = Path(tmp) / "state.json"
        hb.save_state({"a:STOP": 1.0})
        hb.save_state({"b:WARN": 2.0})
        merged = json.loads(hb.STATE_FILE.read_text(encoding="utf-8"))
        assert set(merged) == {"a:STOP", "b:WARN"}, merged
        assert not (Path(tmp) / "state.tmp").exists(), "临时文件必须被 replace 掉"
    print("PASS: heartbeat resolves thread ids and merges dedupe state")


if __name__ == "__main__":
    main()
