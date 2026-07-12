#!/usr/bin/env python3
"""
CodexForge TDD MVP v2 — Example Runner

CLI entry point for running the self-correcting TDD loop on built-in examples
or custom targets.

Usage:
    # Run Example 1 (divide) in mock mode:
    python3 engine/run_example.py --example 1 --mode mock

    # Run Example 2 (CSV parser) in mock mode:
    python3 engine/run_example.py --example 2 --mode mock

    # Run Example 3 (dedup) in mock mode:
    python3 engine/run_example.py --example 3 --mode mock

    # Run with live LLM (requires API key):
    python3 engine/run_example.py --example 1 --mode live

    # Custom target:
    python3 engine/run_example.py --target path/to/buggy.py --task "fix the bug" --mode mock
"""

import os
import sys
import shutil
import argparse
import logging

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.tdd_orchestrator import TDDOrchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RunExample")

# ─── Built-in example definitions ──────────────────────────────

EXAMPLES = {
    1: {
        "name": "Division by Zero",
        "source": "buggy_divide.py",
        "test": "test_buggy_divide.py",
        "task": (
            "Fix the divide() function in buggy_divide.py so that "
            "division by zero returns 0 instead of raising a ZeroDivisionError."
        ),
    },
    2: {
        "name": "CSV Parser (Quoted Fields)",
        "source": "buggy_parser.py",
        "test": "test_buggy_parser.py",
        "task": (
            "Fix the parse_csv_line() function in buggy_parser.py so that "
            "commas inside double-quoted fields are not treated as delimiters. "
            "For example, 'a,\"hello, world\",c' should produce ['a', 'hello, world', 'c']."
        ),
    },
    3: {
        "name": "List Deduplication (Order Preservation)",
        "source": "buggy_dedup.py",
        "test": "test_buggy_dedup.py",
        "task": (
            "Fix the deduplicate() function in buggy_dedup.py so that it "
            "removes duplicates while preserving the order of first occurrence. "
            "Currently it uses sorted(set()) which loses insertion order."
        ),
    },
    4: {
        "name": "Exception Handling (Retry)",
        "source": "buggy_retry.py",
        "test": "test_buggy_retry.py",
        "task": (
            "Fix the retry() function in buggy_retry.py so that it only "
            "catches Exception subclasses and lets KeyboardInterrupt, SystemExit, "
            "and other BaseException subclasses propagate immediately without retrying."
        ),
    },
    5: {
        "name": "Nested List Flattening (Recursive)",
        "source": "buggy_flatten.py",
        "test": "test_buggy_flatten.py",
        "task": (
            "Fix the flatten() function in buggy_flatten.py so that it "
            "recursively flattens arbitrarily nested lists. Currently it only "
            "handles one level of nesting. [1, [2, [3, 4]], 5] should return [1, 2, 3, 4, 5]."
        ),
    },
}


def main():
    parser = argparse.ArgumentParser(
        description="CodexForge TDD MVP v2 — Self-Correcting TDD Loop Runner"
    )

    parser.add_argument(
        "--example",
        type=int,
        choices=[1, 2, 3, 4, 5],
        help="Run a built-in example: 1=divide, 2=csv_parser, 3=dedup, 4=retry, 5=flatten"
    )
    parser.add_argument(
        "--target",
        type=str,
        help="Path to a custom buggy code file (relative to project root)"
    )
    parser.add_argument(
        "--task",
        type=str,
        help="Task description for the TDD loop (required with --target)"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["live", "mock"],
        default="mock",
        help="LLM mode: 'live' (requires API key) or 'mock' (offline). Default: mock"
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="Maximum repair attempts (default: 5)"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.example and not args.target:
        parser.error("Either --example or --target is required.")

    if args.target and not args.task:
        parser.error("--task is required when using --target.")

    # Resolve paths
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    workspace_dir = os.path.join(base_dir, "sandbox", "workspace")
    tests_dir = os.path.join(base_dir, "tests")

    os.makedirs(workspace_dir, exist_ok=True)

    if args.example:
        example = EXAMPLES[args.example]
        source_file = example["source"]
        test_file = example["test"]
        task = example["task"]

        logger.info("=" * 60)
        logger.info(f"CodexForge TDD MVP v2 — Example {args.example}: {example['name']}")
        logger.info(f"Mode: {args.mode}")
        logger.info("=" * 60)

        # Copy fresh buggy code to workspace
        src = os.path.join(tests_dir, source_file)
        dst = os.path.join(workspace_dir, source_file)

        if not os.path.exists(src):
            logger.error(f"Source file not found: {src}")
            sys.exit(1)

        logger.info(f"Copying fresh buggy code: {src} → {dst}")
        shutil.copy2(src, dst)

        # Remove old test file if exists
        old_test = os.path.join(workspace_dir, test_file)
        if os.path.exists(old_test):
            os.remove(old_test)

    else:
        # Custom target
        source_file = os.path.basename(args.target)
        test_file = f"test_{source_file}"
        task = args.task

        logger.info("=" * 60)
        logger.info(f"CodexForge TDD MVP v2 — Custom Target: {source_file}")
        logger.info(f"Mode: {args.mode}")
        logger.info("=" * 60)

        # Copy custom target to workspace
        src = os.path.abspath(args.target)
        dst = os.path.join(workspace_dir, source_file)

        if not os.path.exists(src):
            logger.error(f"Target file not found: {src}")
            sys.exit(1)

        shutil.copy2(src, dst)

        old_test = os.path.join(workspace_dir, test_file)
        if os.path.exists(old_test):
            os.remove(old_test)

    # Run the TDD loop
    orchestrator = TDDOrchestrator(
        workspace_dir=workspace_dir,
        target_file_rel=source_file,
        test_file_rel=test_file,
        mode=args.mode
    )

    success = orchestrator.execute_tdd_loop(task, max_retries=args.max_retries)

    # Print result
    print()
    if success:
        logger.info("=" * 60)
        logger.info("🎉 TDD Loop Completed SUCCESSFULLY!")
        logger.info("=" * 60)
        fixed_path = os.path.join(workspace_dir, source_file)
        with open(fixed_path, "r") as f:
            fixed_code = f.read()
        print(f"\nFixed code ({source_file}):")
        print("─" * 40)
        print(fixed_code)
        print("─" * 40)
    else:
        logger.error("=" * 60)
        logger.error("❌ TDD Loop FAILED.")
        logger.error("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
