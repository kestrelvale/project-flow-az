"""
WikiSkill 命令行入口 (CLI Interface)
提供标准的初始化、编译、评估、演化与状态自检命令
"""

import sys
import argparse
import json
from pathlib import Path
from ..storage.workspace import WorkspaceManager
from ..core.orchestrator import WikiSkillOrchestrator, OrchestratorConfig
from ..core.inference import InferenceAgent


def cmd_init(args):
    ws = WorkspaceManager(args.workspace)
    ws.init_workspace(force=args.force)
    print(f"✅ WikiSkill workspace initialized at: {ws.root}")
    print(f"  ├── raw/traces/    (Append-only immutable traces)")
    print(f"  ├── wiki/          (Persistent knowledge: patterns, index, log, skill-impact)")
    print(f"  └── skills/        (Conditional procedural skills)")


def cmd_status(args):
    ws = WorkspaceManager(args.workspace)
    traces = ws.list_traces()
    patterns = ws.list_patterns()
    skills = ws.list_skills()

    print(f"=== WikiSkill Workspace Status [{ws.root}] ===")
    print(f"📦 Raw Traces:       {len(traces)} items")
    print(f"🧠 Wiki Patterns:    {len(patterns)} patterns")
    print(f"⚡ Active Skills:    {len(skills)} skills")

    if skills:
        print("\nActive Skills:")
        for s in skills:
            print(f"  - {s}")

    if patterns:
        print("\nWiki Patterns:")
        for p in patterns:
            print(f"  - {p}")


def cmd_evolve(args):
    ws = WorkspaceManager(args.workspace)
    ws.init_workspace()

    if not Path(args.train).exists():
        print(f"❌ Training tasks file not found: {args.train}", file=sys.stderr)
        sys.exit(1)
    if not Path(args.val).exists():
        print(f"❌ Validation tasks file not found: {args.val}", file=sys.stderr)
        sys.exit(1)

    with open(args.train, "r", encoding="utf-8") as f:
        train_tasks = json.load(f)
    with open(args.val, "r", encoding="utf-8") as f:
        val_tasks = json.load(f)

    cfg = OrchestratorConfig(
        max_iterations=args.max_iters,
        early_stop_score=args.early_stop,
        verbose=True
    )
    orch = WikiSkillOrchestrator(workspace=ws, config=cfg)
    summary = orch.evolve(train_tasks=train_tasks, val_tasks=val_tasks)

    print("\n=== Evolution Finished ===")
    print(f"Initial Score: {summary.initial_score:.4f} -> Final Best Score: {summary.best_score:.4f}")
    print(f"Iterations: {summary.iterations_run}")
    print(f"Proposals Accepted: {summary.accepted_proposals} | Rejected: {summary.rejected_proposals}")
    print(f"Total Skills: {summary.total_skills} | Total Patterns: {summary.total_patterns}")


def main():
    parser = argparse.ArgumentParser(
        prog="wikiskill",
        description="WikiSkill: Compiling Agent Experience into Persistent Knowledge for Skill Evolution (arXiv:2608.27454)"
    )
    parser.add_argument("--workspace", "-w", default=".", help="Workspace root directory (default: current dir)")

    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # init
    p_init = subparsers.add_parser("init", help="Initialize the WikiSkill three-tier workspace")
    p_init.add_argument("--force", "-f", action="store_true", help="Force overwrite existing templates")

    # status
    p_status = subparsers.add_parser("status", help="Inspect current workspace status (traces, patterns, skills)")

    # evolve
    p_evolve = subparsers.add_parser("evolve", help="Run Algorithm 1 evolution loop on train/val datasets")
    p_evolve.add_argument("--train", required=True, help="Path to train tasks JSON")
    p_evolve.add_argument("--val", required=True, help="Path to val tasks JSON")
    p_evolve.add_argument("--max-iters", type=int, default=5, help="Maximum evolution iterations")
    p_evolve.add_argument("--early-stop", type=float, default=1.0, help="Target score for early termination")

    args = parser.parse_args()
    if not args.subcommand:
        parser.print_help()
        sys.exit(0)

    if args.subcommand == "init":
        cmd_init(args)
    elif args.subcommand == "status":
        cmd_status(args)
    elif args.subcommand == "evolve":
        cmd_evolve(args)


if __name__ == "__main__":
    main()
