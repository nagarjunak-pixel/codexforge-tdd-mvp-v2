"""
CodexForge TDD Orchestrator — v2

Coordinates the self-correcting RED→GREEN TDD loop:
1. Reads the target buggy code file.
2. Prompts the LLM to generate a failing reproduction test.
3. Runs the test in the sandbox to verify failure (RED).
4. Prompts the LLM to fix the code.
5. Applies the fix via ACP buffer sync.
6. Runs the test again to verify success (GREEN).
7. If still failing, retries with error feedback (up to max_retries).

v2 improvements over v1:
- Mode-aware (live vs mock, no silent fallback)
- Supports multiple target files (not just one hardcoded example)
- Properly resolves Docker volume-mounted paths
- Better error messages and logging
"""

import os
import re
import sys
import subprocess
import logging
from typing import Tuple, Optional

# Add parent directory to path for sibling module imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from router.llm_client import LLMClient
from acp.acp_client import ACPClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TDDOrchestrator")


class TDDOrchestrator:
    def __init__(
        self,
        workspace_dir: str,
        target_file_rel: str,
        test_file_rel: str,
        mode: str = "mock"
    ):
        """
        Initialize the TDD orchestrator.

        Args:
            workspace_dir: Absolute path to the workspace directory on host.
            target_file_rel: Path to the buggy code file relative to workspace.
            test_file_rel: Path to the test file relative to workspace.
            mode: "live" or "mock" — passed directly to LLMClient.
        """
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.target_file_rel = target_file_rel
        self.test_file_rel = test_file_rel
        self.mode = mode

        self.target_file_abs = os.path.join(self.workspace_dir, target_file_rel)
        self.test_file_abs = os.path.join(self.workspace_dir, test_file_rel)

        # Initialize LLM client with explicit mode
        self.llm = LLMClient(mode=self.mode)

        # Initialize ACP client for buffer sync
        self.acp = ACPClient(f"file://{self.target_file_abs}")

        # Detect if Docker sandbox is available
        self.use_docker = self._check_docker_container()

    def _check_docker_container(self) -> bool:
        """Check if the Docker sandbox container is running."""
        sandbox_dir = os.path.join(os.path.dirname(__file__), "..", "sandbox")
        sandbox_dir = os.path.abspath(sandbox_dir)
        try:
            res = subprocess.run(
                ["docker", "compose", "ps", "--status", "running", "-q"],
                cwd=sandbox_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5
            )
            is_active = bool(res.stdout.strip())
            if is_active:
                logger.info("✓ Docker sandbox container detected and running.")
                return True
        except FileNotFoundError:
            logger.info("Docker CLI not found on PATH.")
        except subprocess.TimeoutExpired:
            logger.warning("Docker check timed out.")
        except Exception as e:
            logger.debug(f"Docker check failed: {e}")

        logger.info("Docker sandbox not available. Using local subprocess fallback.")
        return False

    def run_in_sandbox(self, command: str) -> Tuple[int, str, str]:
        """
        Run a shell command inside the Docker sandbox, or fall back to local subprocess.

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        if self.use_docker:
            sandbox_dir = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "sandbox")
            )
            full_cmd = [
                "docker", "compose", "exec", "-T",
                "sandbox_service", "sh", "-c", command
            ]
            logger.info(f"[Docker] Executing: {command}")
            res = subprocess.run(
                full_cmd,
                cwd=sandbox_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120
            )
            return res.returncode, res.stdout, res.stderr
        else:
            logger.info(f"[Local] Executing: {command}")
            env = os.environ.copy()
            env["PYTHONPATH"] = self.workspace_dir
            res = subprocess.run(
                command,
                shell=True,
                cwd=self.workspace_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                timeout=120
            )
            return res.returncode, res.stdout, res.stderr

    def read_file(self, abs_path: str) -> str:
        """Read file contents, return empty string if not found."""
        if os.path.exists(abs_path):
            with open(abs_path, "r") as f:
                return f.read()
        return ""

    def write_file(self, abs_path: str, content: str):
        """Write content to file, creating parent directories if needed."""
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w") as f:
            f.write(content)

    def extract_code_block(self, text: str) -> str:
        """Extract Python code from a markdown code block in LLM output."""
        match = re.search(r"```(?:python)?\n(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()

    def execute_tdd_loop(
        self,
        task_description: str,
        max_retries: int = 5
    ) -> bool:
        """
        Execute the self-correcting TDD loop.

        Args:
            task_description: What bug to fix or feature to implement.
            max_retries: Maximum repair attempts before giving up.

        Returns:
            True if GREEN state was achieved, False otherwise.
        """
        logger.info("=" * 60)
        logger.info(f"TDD Loop Starting")
        logger.info(f"  Task: {task_description}")
        logger.info(f"  Target: {self.target_file_rel}")
        logger.info(f"  Mode: {self.mode}")
        logger.info(f"  Sandbox: {'Docker' if self.use_docker else 'Local'}")
        logger.info("=" * 60)

        # ─── Step 1: Read original code ─────────────────────────
        original_code = self.read_file(self.target_file_abs)
        if not original_code.strip():
            logger.error(f"Target file is empty or not found: {self.target_file_abs}")
            return False

        logger.info(
            f"Read target file: {self.target_file_rel} "
            f"({len(original_code)} chars, {len(original_code.splitlines())} lines)"
        )

        # ─── Step 2: Generate failing reproduction test ─────────
        logger.info("")
        logger.info("─── STEP 1: Generate Failing Test (RED) ───")
        test_prompt = f"""
We have a target file '{self.target_file_rel}' containing the following code:
```python
{original_code}
```

Task specification: {task_description}

Please write a failing pytest test function that reproduces the bug or missing feature specified.
Write ONLY a valid Python test block enclosed in ```python ... ``` tags.
The test must fail on the current implementation.
Import the function directly from '{os.path.splitext(self.target_file_rel)[0]}'.
"""
        system_instruction = (
            "You are a TDD test engineer. You write failing reproduction pytest cases."
        )
        test_response_raw = self.llm.generate_completion(
            test_prompt, system_instruction=system_instruction
        )
        test_code = self.extract_code_block(test_response_raw)

        # Write test file
        self.write_file(self.test_file_abs, test_code)
        logger.info(f"Wrote test file: {self.test_file_rel}")
        logger.info(f"Test code:\n{test_code}")

        # ─── Step 3: Verify test fails (RED) ────────────────────
        logger.info("")
        logger.info("─── STEP 2: Verify Test Fails (RED State) ───")
        exit_code, stdout, stderr = self.run_in_sandbox(
            f"python3 -m pytest {self.test_file_rel} -v"
        )

        if exit_code == 0:
            logger.error(
                "✗ Reproduction test PASSED on buggy code! "
                "TDD rules require a FAILING test first. Aborting."
            )
            logger.error(f"pytest output:\n{stdout}")
            return False

        logger.info("✓ RED state verified — reproduction test fails as expected.")
        logger.info(f"Failure output:\n{stdout}\n{stderr}")

        # ─── Step 4: Repair loop (attempt GREEN) ────────────────
        logger.info("")
        logger.info("─── STEP 3: Code Repair Loop (Iterating to GREEN) ───")

        attempt = 0
        current_code = original_code

        while attempt < max_retries:
            attempt += 1
            logger.info(f"")
            logger.info(f"── Repair attempt {attempt}/{max_retries} ──")

            repair_prompt = f"""
We have a target file '{self.target_file_rel}' containing the following code:
```python
{current_code}
```

We wrote the following reproduction test in '{self.test_file_rel}':
```python
{test_code}
```

When we executed the test suite, it failed with the following output:
```
{stdout}
{stderr}
```

Please fix/modify the code in '{self.target_file_rel}' so that the test passes.
Provide the entire corrected code inside a ```python ... ``` block.
"""
            system_instruction = (
                "You are an expert TDD developer. You write correct, bug-free "
                "implementations that pass test suites."
            )
            repair_response_raw = self.llm.generate_completion(
                repair_prompt, system_instruction=system_instruction
            )
            proposed_code = self.extract_code_block(repair_response_raw)

            logger.info(f"Proposed fix:\n{proposed_code}")

            # Apply via ACP buffer sync
            logger.info("Syncing buffer changes via ACP JSON-RPC Adapter...")
            payload = self.acp.generate_did_change_payload(current_code, proposed_code)
            new_code_state = ACPClient.apply_did_change_payload(payload, current_code)

            # Write updated code
            self.write_file(self.target_file_abs, new_code_state)
            current_code = new_code_state

            # Run tests (GREEN check)
            logger.info("Running test suite...")
            exit_code, stdout, stderr = self.run_in_sandbox(
                f"python3 -m pytest {self.test_file_rel} -v"
            )

            if exit_code == 0:
                logger.info("")
                logger.info("=" * 60)
                logger.info(f"✓ GREEN STATE ACHIEVED on attempt {attempt}!")
                logger.info("=" * 60)
                logger.info(f"pytest output:\n{stdout}")
                return True

            logger.warning(
                f"✗ Attempt {attempt} failed — tests still not passing."
            )
            logger.warning(f"pytest output:\n{stdout}\n{stderr}")

        logger.error("")
        logger.error("=" * 60)
        logger.error(f"✗ FAILED: Could not achieve GREEN state after {max_retries} attempts.")
        logger.error("=" * 60)
        return False
