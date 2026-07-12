# CodexForge TDD MVP v2

A self-correcting test-driven development (TDD) sandbox that enforces writing a failing reproduction test first (RED), modifying source code via buffer updates, and verifying test completion (GREEN) inside an isolated execution environment.

**v2** closes four gaps from the v1 baseline: real VS Code extension, tested Docker path, 3 diverse examples, and explicit mode control (no silent mock fallback).

---

## Repository Structure

```
codexforge_mvp_v2/
├── DESIGN.md              # High-level system design
├── PLAN.md                # Phased build plan with acceptance criteria
├── ARCHITECTURE.png       # System architecture diagram
├── README.md              # This file
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
│   └── llm_client.py       # LLM API client (Anthropic/OpenAI) with mode control
└── tests/
    ├── buggy_divide.py     # Example 1: Division by zero
    ├── buggy_parser.py     # Example 2: CSV parser with quoted fields
    └── buggy_dedup.py      # Example 3: List dedup with order preservation
```

---

## Prerequisites

- **Python 3.11+** (required)
- **Docker** (optional — falls back to local subprocess if not available)
- **API Key** (optional — required for `--mode=live` only)

---

## Quick Start (Mock Mode — No Docker, No API Key)

```bash
cd codexforge_mvp_v2

# Run Example 1: Division by zero
python3 engine/run_example.py --example 1 --mode mock

# Run Example 2: CSV parser
python3 engine/run_example.py --example 2 --mode mock

# Run Example 3: List deduplication
python3 engine/run_example.py --example 3 --mode mock
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

# Verify exec works
docker compose exec sandbox_service python3 -c "import pytest; print('pytest OK')"

cd ..

# Now run examples — they'll automatically use Docker
python3 engine/run_example.py --example 1 --mode mock
```

The orchestrator auto-detects a running Docker container and routes test execution through `docker compose exec` instead of local subprocess.

---

## Running with Live LLM (API Key Required)

```bash
# Set your API key (choose one)
export ANTHROPIC_API_KEY="sk-ant-..."
# or
export OPENAI_API_KEY="sk-..."

# Optionally set a specific model
export CODEXFORGE_MODEL="claude-3-5-sonnet-20241022"

# Run with live LLM
python3 engine/run_example.py --example 1 --mode live
```

**Important**: Running with `--mode=live` without an API key will produce a clear error message — it will NOT silently fall back to mock mode. This is intentional.

---

## Custom Targets

```bash
# Fix your own buggy code
python3 engine/run_example.py \
    --target path/to/your/buggy_file.py \
    --task "Fix the function so it handles edge case X" \
    --mode live
```

---

## VS Code Extension

The `acp/` directory contains a real VS Code extension:

### Install for Development

```bash
# Open VS Code with the extension in development mode
cd codexforge_mvp_v2/acp
code --extensionDevelopmentPath=.
```

### Start the ACP Server

Before using the extension, start the Python ACP server:

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

## v1 → v2 Changelog

| Area | v1 | v2 |
|------|----|----|
| ACP Extension | Stub `package.json` only | Real `extension.js` with activation events, commands, TCP client |
| Docker Sandbox | Untested volume mount | Fixed mount, healthcheck, verified exec path |
| Examples | 1 hardcoded `divide()` | 3 diverse examples (divide, CSV parser, dedup) |
| Mode Control | Silent mock fallback | Explicit `--mode` flag; hard error without API key in live mode |
| Model Config | Hardcoded model names | Configurable via `CODEXFORGE_MODEL` env var |
| CLI | No CLI interface | Full argparse with `--example`, `--mode`, `--target`, `--task` |

---

## Deferred (Not in MVP)

- **BrandStream AI** — Video generation, audio pipelines, ComfyUI
- **gVisor / Tailscale** — Using standard Docker isolation
- **AISG / diffSAE** — No activation steering; prompt-based safety only
- **3D Dashboard / Memory Graph** — CLI logging only
- **REPL State Persistence** — Fundamentally impossible for dynamic objects
