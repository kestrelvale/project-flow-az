# 规格点回收台账 · PFP-PHASE-GATE-TRUTH-20260927

- [x] SPE-1 | 相位必须由 flow/plan.md 的分区位置推导（`[ ]`=plan、`[-]`=execute、history=review），不得用卡自报的 mode | 证据：scripts/flow-boot.py 新增 phase_from_plan()；tests/test-phase-gate-truth.py::test_phase_from_plan_section_not_card_mode 绿
- [x] SPE-2 | 卡文件名（T1-login）与计划表 ticket_id（T1）不一致时仍要能定位 | 证据：phase_from_plan 同时用文件名与 read_card().ticket_id 作别名匹配；真机复现前红（返回 plan）后绿
- [x] SPE-3 | 斩断自证循环：移除「phase==plan 则 mode 必须 plan」这条恒真校验，改守单向流转（未交付卡不得自报 review/handoff） | 证据：tests/test-phase-gate-truth.py::test_gate_blocks_skipping_phases 绿
- [x] SPE-4 | `[ ]` 区放 mode: execute 的实现卡必须放行（相位与 mode 是两个轴，不得误杀） | 证据：tests/test-phase-gate-truth.py::test_execute_card_in_active_area_is_allowed 绿
- [x] SPE-5 | 端到端：boot 必须以真实相位跑门禁并在卡撒谎时报 [plan] 失败 | 证据：tests/test-phase-gate-truth.py::test_boot_uses_true_phase_not_card_mode 绿；篡改回 mode-as-phase 后该用例变红
