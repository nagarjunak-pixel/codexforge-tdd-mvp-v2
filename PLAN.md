# CodexForge TDD MVP v2 — Phased Build Plan

## Phased Milestones

### Milestone 1: Docker Execution Sandbox (`sandbox/`)

**Goal**: Build a tested, isolated runtime sandbox using Docker Compose to execute test runners and scripts.

**Deliverables**:
* `sandbox/Dockerfile` — Python 3.11-slim base with pytest and ruff. Healthcheck included.
* `sandbox/docker-compose.yml` — Volume-mounts project workspace, named container, healthcheck with retry policy.

**Acceptance Criteria**:
* `docker compose up -d` starts successfully and passes healthcheck.
* `docker compose exec sandbox_service python3 -m pytest /workspace/test_sample.py` runs and returns stdout/stderr + exit code.
* Volume changes on host are immediately visible inside container.

**v1→v2 Improvement**: Volume mount now points to the actual project workspace, not sandbox-internal `./workspace`. Healthcheck verifies container is ready before exec.

---

### Milestone 2: Direct Model Router (`router/`)

**Goal**: Implement a robust, mode-aware LLM API client with explicit error handling.

**Deliverables**:
* `router/llm_client.py` — Supports Anthropic Claude and OpenAI GPT-4o with configurable model name.

**Acceptance Criteria**:
* `mode="live"` without API key raises `ConfigurationError` with clear instructions.
* `mode="mock"` returns correct mock responses for all 3 example functions.
* HTTP 429 triggers exponential backoff retry (up to 5 attempts).
* Model name configurable via `CODEXFORGE_MODEL` env var.

**v1→v2 Improvement**: No silent mock fallback. Hard error on missing key in live mode. Configurable model name.

---

### Milestone 3: Real VS Code ACP Extension (`acp/`)

**Goal**: Build a working VS Code extension that sends buffer diffs to the agent process.

**Deliverables**:
* `acp/package.json` — Full extension manifest with activation events and contribution points.
* `acp/extension.js` — Extension entry point with `activate()`, command registration, TCP JSON-RPC client.
* `acp/acp_client.py` — Python TCP server on port 9120 + programmatic client API.
* `acp/diff_solver.py` — Three-way merge helper.

**Acceptance Criteria**:
* VS Code recognizes the extension and registers commands (`codexforge.sendBuffer`, `codexforge.startTDD`).
* Extension sends valid JSON-RPC payloads to `localhost:9120`.
* Python server receives and parses payloads correctly.
* `diff_solver.py` correctly merges non-overlapping changes and marks conflicts.

**v1→v2 Improvement**: Real `extension.js` with lifecycle hooks instead of a manifest stub.

---

### Milestone 4: TDD Orchestrator Engine (`engine/`)

**Goal**: Enforce the test-driven development loop with mode awareness and multi-example support.

**Deliverables**:
* `engine/tdd_orchestrator.py` — Core TDD loop with strict RED→GREEN enforcement.
* `engine/run_example.py` — CLI entry point with argparse for `--example`, `--mode`, `--task`, `--target`.

**Acceptance Criteria**:
* Orchestrator rejects code edits if no failing test has been verified (RED state not achieved).
* Retry loop capped at 5 attempts.
* `--mode=mock` runs end-to-end offline for all 3 examples.
* `--mode=live` without API key produces a clear error message.

**v1→v2 Improvement**: CLI interface, multi-example support, mode-aware orchestration.

---

### Milestone 5: Diverse Test Fixtures (`tests/`)

**Goal**: Demonstrate the TDD loop is general-purpose, not a one-trick mock.

**Deliverables**:
* `tests/buggy_divide.py` — Integer division by zero (carried from v1).
* `tests/buggy_parser.py` — CSV parser that mishandles quoted fields with commas.
* `tests/buggy_dedup.py` — List deduplication that doesn't preserve insertion order.

**Acceptance Criteria**:
* Each buggy function has a specific, reproducible bug.
* Mock mode generates appropriate failing tests and fixes for each function.
* `run_example.py --example N --mode mock` completes RED→GREEN for all N ∈ {1, 2, 3}.

**v1→v2 Improvement**: 3 diverse examples instead of 1 hardcoded `divide()`.

---

### Milestone 6: End-to-End Validation & Documentation

**Goal**: Verify the complete system works and document setup/usage.

**Deliverables**:
* `README.md` — Complete setup and run instructions for all modes.
* Syntax check all Python files.
* Run all 3 mock examples end-to-end.
* Verify ARCHITECTURE.png is a valid image.

**Acceptance Criteria**:
* All Python files pass `py_compile`.
* All 3 mock examples complete RED→GREEN.
* README covers: with/without Docker, with/without API key, VS Code extension install.
* `find codexforge_mvp_v2/ -type f | sort` lists all expected files.
