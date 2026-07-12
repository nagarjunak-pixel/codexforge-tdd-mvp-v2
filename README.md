# CodexForge TDD MVP v2

[![CI](https://github.com/nagarjunak-pixel/codexforge-tdd-mvp-v2/actions/workflows/ci.yml/badge.svg)](https://github.com/nagarjunak-pixel/codexforge-tdd-mvp-v2/actions/workflows/ci.yml)

A self-correcting test-driven development (TDD) sandbox that enforces writing a failing reproduction test first (RED), modifying source code via buffer updates, and verifying test completion (GREEN) inside an isolated execution environment.

**v2** closes four gaps from the v1 baseline: real VS Code extension, tested Docker path, 5 diverse examples, and explicit mode control (no silent mock fallback).

---

## Repository Structure

```
codexforge_mvp_v2/
├── DESIGN.md              # High-level system design
├── PLAN.md                # Phased build plan with acceptance criteria
├── ARCHITECTURE.png       # System architecture diagram
├── README.md              # This file
├── requirements.txt       # Python dependencies
├── sandbox/
│   ├── Dockerfile         # Python 3.11 sandbox with pytest + ruff
│   ├── docker-compose.yml # Container orchestration with healthcheck
│   └── workspace/         # Volume-mounted workspace for test execution
├── acp/
│   ├── package.json       # Real VS Code extension manifest
│   ├── extension.js       # VS Code extension (commands + TCP JSON-RPC)
│   ├── acp_client.py      # Python ACP server (port 9120) + client API
│   └── diff_solver.py     # Three-way merge (Diff3) conflict resolver
├── engine/
│   ├── tdd_orchestrator.py # Core RED→GREEN TDD loop orchestrator
│   └── run_example.py      # CLI entry point with argparse
├── router/
│   └── llm_client.py       # LLM API client (Anthropic/OpenAI/OpenRouter)
├── tests/
│   ├── buggy_divide.py     # Example 1: Division by zero
│   ├── buggy_parser.py     # Example 2: CSV parser with quoted fields
│   ├── buggy_dedup.py      # Example 3: List dedup with order preservation
│   ├── buggy_retry.py      # Example 4: Exception handling (retry)
│   ├── buggy_flatten.py    # Example 5: Recursive nested list flattening
│   ├── test_llm_client.py  # Unit tests for LLM client (12 tests)
│   ├── test_diff_solver.py # Unit tests for Diff3 solver (8 tests)
│   └── test_acp_client.py  # Unit tests for ACP client (6 tests)
└── .github/workflows/
    └── ci.yml              # Full CI: syntax, unit tests, mock examples, Docker, VS Code
```

---

## Prerequisites

- **Python 3.9+** (required)
- **Docker** (optional — falls back to local subprocess if not available)
- **API Key** (optional — required for `--mode=live` only)

```bash
pip install -r requirements.txt
```

---

## Quick Start (Mock Mode — No Docker, No API Key)

```bash
cd codexforge_mvp_v2

# Run any of the 5 built-in examples
python3 engine/run_example.py --example 1 --mode mock   # Division by zero
python3 engine/run_example.py --example 2 --mode mock   # CSV parser
python3 engine/run_example.py --example 3 --mode mock   # List deduplication
python3 engine/run_example.py --example 4 --mode mock   # Exception handling (retry)
python3 engine/run_example.py --example 5 --mode mock   # Nested list flattening
```

Each example demonstrates the full RED→GREEN TDD loop:
1. Reads the buggy code
2. Generates a failing reproduction test (RED)
3. Verifies the test fails
4. Generates a code fix
5. Applies the fix via ACP buffer sync
6. Verifies the test passes (GREEN)

---

## Running with Docker Sandbox

```bash
cd codexforge_mvp_v2/sandbox

# Build and start the sandbox container
docker compose up -d

# Verify it's healthy
docker compose ps

cd ..

# Now run examples — they'll automatically use Docker
python3 engine/run_example.py --example 1 --mode mock
```

The orchestrator auto-detects a running Docker container and routes test execution through `docker compose exec` instead of local subprocess.

---

## Running with Live LLM (API Key Required)

Three providers are supported — the client auto-detects which key you've set:

```bash
# Option A: Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."
python3 engine/run_example.py --example 1 --mode live

# Option B: OpenAI
export OPENAI_API_KEY="sk-..."
python3 engine/run_example.py --example 1 --mode live

# Option C: OpenRouter (100+ models, pay-per-token)
export OPENROUTER_API_KEY="sk-or-..."
python3 engine/run_example.py --example 1 --mode live
```

### Configure Model

```bash
# Override the default model for any provider
export CODEXFORGE_MODEL="google/gemini-2.5-flash"    # OpenRouter
export CODEXFORGE_MODEL="claude-3-5-sonnet-20241022"  # Anthropic
export CODEXFORGE_MODEL="gpt-4o"                      # OpenAI
```

**Important**: Running with `--mode=live` without an API key will produce a clear error message — it will NOT silently fall back to mock mode. This is intentional.

---

## Custom Targets

Fix your own buggy code — no need to add it to the built-in examples:

```bash
python3 engine/run_example.py \
    --target path/to/your/buggy_file.py \
    --task "Fix the function so it handles edge case X" \
    --mode live
```

---

## Unit Tests

```bash
# Run all 26 unit tests
python3 -m pytest tests/test_llm_client.py tests/test_diff_solver.py tests/test_acp_client.py -v
```

---

## VS Code Extension

The `acp/` directory contains a real VS Code extension:

### Install for Development

```bash
cd codexforge_mvp_v2/acp
code --extensionDevelopmentPath=.
```

### Start the ACP Server

```bash
python3 acp/acp_client.py
```

This starts a TCP server on `localhost:9120` that receives JSON-RPC payloads from the VS Code extension.

### Available Commands

- **CodexForge: Send Current Buffer to Agent** — Sends the current editor buffer as a `textDocument/didChange` payload.
- **CodexForge: Start TDD Loop** — Prompts for a task description and initiates the TDD loop.

### Configuration

In VS Code settings:
- `codexforge.agentHost` — ACP server hostname (default: `localhost`)
- `codexforge.agentPort` — ACP server port (default: `9120`)

---

## Built-in Examples

| # | Name | Bug | Fix |
|---|------|-----|-----|
| 1 | Division by Zero | `return a / b` raises `ZeroDivisionError` | Guard `if b == 0: return 0` |
| 2 | CSV Parser | Splits on ALL commas, ignoring quotes | Track `in_quotes` state |
| 3 | List Dedup | `sorted(set())` loses insertion order | `seen = set()` + ordered loop |
| 4 | Exception Handling | `except BaseException` swallows `KeyboardInterrupt` | `except Exception` only |
| 5 | Nested Flatten | Only one level deep: `result.extend(item)` | Recursive: `result.extend(flatten(item))` |

---

## CI Pipeline

The GitHub Actions CI runs on every push and PR:

| Job | Tests |
|-----|-------|
| **Syntax Check** | Compiles all Python files |
| **Unit Tests** | 26 module-level tests |
| **Mock Examples (1–5)** | 5 parallel TDD loops |
| **Docker Sandbox** | All 5 examples in container |
| **VS Code Extension** | package.json + extension.js validation |

---

## v1 → v2 Changelog

| Area | v1 | v2 |
|------|----|-----|
| ACP Extension | Stub `package.json` only | Real `extension.js` with activation events, commands, TCP client |
| Docker Sandbox | Untested volume mount | Fixed mount, healthcheck, verified exec path |
| Examples | 1 hardcoded `divide()` | 5 diverse examples (divide, CSV, dedup, retry, flatten) |
| Mode Control | Silent mock fallback | Explicit `--mode` flag; hard error without API key in live mode |
| Providers | Anthropic + OpenAI only | + OpenRouter (100+ models) |
| Model Config | Hardcoded model names | Configurable via `CODEXFORGE_MODEL` env var |
| CLI | No CLI interface | Full argparse with `--example`, `--mode`, `--target`, `--task` |
| Tests | None | 26 unit tests + CI pipeline |
| Live Verified | Mock only | Gemini 2.5 Flash via OpenRouter — 5/5 GREEN |

---

## Deferred (Not in MVP)

- **BrandStream AI** — Video generation, audio pipelines, ComfyUI
- **gVisor / Tailscale** — Using standard Docker isolation
- **AISG / diffSAE** — No activation steering; prompt-based safety only
- **3D Dashboard / Memory Graph** — CLI logging only
- **REPL State Persistence** — Fundamentally impossible for dynamic objects
