# CodexForge TDD MVP v2 — High-Level Design

## 1. Overview & Purpose

The **CodexForge Self-Correcting TDD Sandbox MVP v2** is an improved vertical slice focusing on autonomous test-driven development (TDD) inside an isolated Docker sandbox. The system enforces a strict RED→GREEN TDD loop:

1. Developer specifies a bug or requirement.
2. Agent writes a failing reproduction test.
3. Test runs inside the sandbox to confirm failure (**RED**).
4. Agent prompts the LLM to modify source code.
5. Test runs inside the sandbox to verify the fix (**GREEN**).
6. If verification fails, feed errors back to the LLM and retry (max 5 attempts).

### v1 → v2 Improvements

| Area | v1 (Baseline) | v2 (This Build) |
|------|--------------|-----------------|
| **ACP Adapter** | Stub `package.json`; Python-only simulated client | Real VS Code extension (`extension.js`) with activation events, commands, and JSON-RPC over TCP to a Python server |
| **Docker Sandbox** | Dockerfile exists but volume mounts `./workspace` (sandbox-internal); untested exec path | Fixed volume mount to project workspace; healthcheck; verified `docker compose exec` path; graceful local fallback |
| **Example Coverage** | Single `divide()` mock with hardcoded keyword matching | 3 diverse examples (division-by-zero, CSV parser, list dedup) with per-function mock responses |
| **Mode Control** | Silent fallback to mock when no API key is set | Explicit `--mode` flag; `live` mode hard-errors without a key; `mock` requires opt-in; configurable model via `CODEXFORGE_MODEL` env var |

All other components from the enterprise proposal (BrandStream AI, gVisor, Tailscale network overlays, weight activation steering / diffSAE, and 3D dashboards) remain explicitly deferred.

---

## 2. Component Architecture

The MVP consists of four main modules plus a test fixtures directory:

```
┌─────────────────────────────────────────────────────────────────┐
│                      Host Machine / IDE                        │
│                                                                │
│  ┌──────────────────────┐       ┌──────────────────────────┐   │
│  │  VS Code Extension   │──TCP──│  ACP Python Server       │   │
│  │  (acp/extension.js)  │ 9120  │  (acp/acp_client.py)     │   │
│  │  Sends JSON-RPC      │       │  Receives & applies diffs│   │
│  │  textDocument/did    │       └────────────┬─────────────┘   │
│  │  Change payloads     │                    │                 │
│  └──────────────────────┘                    ▼                 │
│                              ┌──────────────────────────────┐  │
│                              │  TDD Orchestrator Engine     │  │
│                              │  (engine/tdd_orchestrator.py)│  │
│                              │  Enforces RED→GREEN loop     │  │
│                              │  Max 5 retry attempts        │  │
│                              └──────────┬───────────────────┘  │
│                                         │                      │
│                    ┌────────────────────┬┘                      │
│                    ▼                    ▼                       │
│  ┌──────────────────────┐  ┌──────────────────────────────┐    │
│  │  Direct LLM Router   │  │  Docker Execution Sandbox    │    │
│  │  (router/llm_client) │  │  (sandbox/)                  │    │
│  │  Claude / GPT-4o     │  │  pytest + ruff inside        │    │
│  │  Retry on 429        │  │  container; volume-mounted   │    │
│  │  Configurable model  │  │  workspace                   │    │
│  │  Hard error if no key│  │  Falls back to local subprocess│  │
│  └──────────────────────┘  └──────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### A. Real VS Code ACP Extension (`acp/`)

* **Role**: Bridges the IDE editor to the agent via the Agent Client Protocol.
* **Components**:
  * `extension.js` — Real VS Code extension with `activate()` lifecycle. Registers two commands:
    * `codexforge.sendBuffer` — Captures active editor content, diffs against last snapshot, sends JSON-RPC `textDocument/didChange` to `localhost:9120`.
    * `codexforge.startTDD` — Prompts for task description, sends to orchestrator.
  * `package.json` — Full extension manifest with `activationEvents`, `contributes.commands`, engine compatibility.
  * `acp_client.py` — Python TCP server on port 9120 that receives JSON-RPC payloads from the extension. Also provides programmatic client API for the orchestrator.
  * `diff_solver.py` — Three-way merge (Diff3) for overlapping human-agent modifications.

### B. Docker Execution Sandbox (`sandbox/`)

* **Role**: Isolated runtime for test execution and static analysis.
* **Components**:
  * `Dockerfile` — `python:3.11-slim` base with `pytest` and `ruff`. Includes a healthcheck.
  * `docker-compose.yml` — Volume-mounts the project workspace (not sandbox-internal). Named container `codexforge_sandbox_v2`. Healthcheck with retry policy.
* **Fallback**: If Docker is not running, the orchestrator gracefully falls back to local subprocess execution with `PYTHONPATH` isolation.

### C. TDD Orchestrator Engine (`engine/`)

* **Role**: Coordinates the core RED→GREEN loop with strict enforcement.
* **Protocol enforcement**:
  * Rejects code changes unless a failing test was written and verified first.
  * Retry loop hard-capped at 5 attempts to prevent runaway billing.
* **Components**:
  * `tdd_orchestrator.py` — Core loop logic. Mode-aware (live vs mock).
  * `run_example.py` — CLI entry point with `argparse` for `--example`, `--mode`, `--target`, `--task`.

### D. Direct Model Router (`router/`)

* **Role**: LLM API communication with explicit mode control.
* **Components**:
  * `llm_client.py` — Supports Anthropic and OpenAI. Model name configurable via `CODEXFORGE_MODEL` env var. Exponential backoff on HTTP 429.
* **Mode control**:
  * `mode="live"` — Requires `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`. Raises `ConfigurationError` if missing.
  * `mode="mock"` — Uses rule-based mock responses keyed on function names. Must be explicitly requested.

---

## 3. Data Flow

1. **Goal Input**: Developer specifies target task via CLI (`--task "fix the CSV parser"`) or VS Code command.
2. **ACP Buffer Read**: The ACP client captures active code file states (from VS Code extension or direct file read).
3. **Failing Test Synthesis**: Orchestrator prompts LLM to generate a reproduction test based on the goal and code state.
4. **RED Verification**: Orchestrator writes the test to workspace, runs test suite in sandbox, verifies failure.
5. **Code Repair Synthesis**: Orchestrator prompts LLM to fix the buggy code, feeding the failure traceback.
6. **ACP Buffer Sync**: LLM's proposed change is converted to a JSON-RPC `textDocument/didChange` payload and applied.
7. **GREEN Verification**: Orchestrator runs test suite in sandbox.
   * If passes → Exit success.
   * If fails → Feed traceback back to LLM, request new fix, repeat from step 5 (up to 5 retries).

---

## 4. Technology Choices & Tradeoffs

| Choice | Rationale |
|--------|-----------|
| **Python for engine, router, ACP server** | Fast prototyping, native subprocess handling, official LLM SDK support |
| **JavaScript for VS Code extension** | Required by the VS Code extension API; kept minimal (no build step, no TypeScript compilation required) |
| **Docker Compose over gVisor** | Developer convenience over hypervisor isolation; satisfies MVP without custom kernel headers |
| **TCP JSON-RPC over WebSocket** | Simpler implementation, no dependency on WS libraries, sufficient for local-only communication |
| **CLI ACP client alongside VS Code** | Allows running the full TDD loop from terminal without an active IDE, while the VS Code extension provides the real integration |
| **Explicit mode flag** | Prevents users from accidentally running mock mode thinking they're hitting a real LLM |

---

## 5. Deferrals & Future Scope

As recommended in the solo-founder MVP review, the following are explicitly deferred:

* **BrandStream AI**: No video generation, audio overlays, voice stream gateways, or ComfyUI workflows.
* **gVisor & Tailscale**: Standard Docker daemon isolation only.
* **AISG Safety Gatekeeper / diffSAE**: No sparse autoencoder activation steering. Rely on prompt instructions and simple output parsing.
* **3D Office Dashboard / Memory Graph**: Standard CLI logging and markdown files only.
* **REPL state persistence**: Deferred due to fundamental impossibility of serializing dynamic objects (database connections, sockets).
