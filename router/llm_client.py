"""
CodexForge Direct LLM Router — v2

Supports Anthropic Claude and OpenAI GPT-4o with:
- Configurable model name via CODEXFORGE_MODEL env var
- Explicit mode control: "live" (requires API key) or "mock" (offline, opt-in only)
- Hard error if mode=live and no API key is set (no silent fallback)
- Exponential backoff retry on HTTP 429 rate limits
"""

import os
import re
import time
import json
import logging
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("LLMClient")


class ConfigurationError(Exception):
    """Raised when the LLM client is misconfigured (e.g., missing API key in live mode)."""
    pass


class LLMClient:
    def __init__(self, mode: str = "mock", provider: Optional[str] = None):
        """
        Initialize the LLM client.

        Args:
            mode: "live" (requires API key) or "mock" (offline, rule-based responses).
                  No silent fallback — you must explicitly choose.
            provider: "anthropic", "openai", or "openrouter". Auto-detected from available keys if not set.
        """
        self.mode = mode.lower()
        if self.mode not in ("live", "mock"):
            raise ConfigurationError(
                f"Invalid mode '{self.mode}'. Must be 'live' or 'mock'."
            )

        self.anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        self.openai_key = os.environ.get("OPENAI_API_KEY")
        self.openrouter_key = os.environ.get("OPENROUTER_API_KEY")

        # Determine provider
        if provider:
            self.provider = provider.lower()
        elif self.anthropic_key:
            self.provider = "anthropic"
        elif self.openrouter_key:
            self.provider = "openrouter"
        elif self.openai_key:
            self.provider = "openai"
        else:
            self.provider = None

        # Configurable model name
        self.model_name = os.environ.get("CODEXFORGE_MODEL")

        if self.mode == "live":
            if not self.provider:
                raise ConfigurationError(
                    "\n" + "=" * 60 + "\n"
                    "ERROR: mode='live' but no API key found!\n\n"
                    "Set one of the following environment variables:\n"
                    "  export ANTHROPIC_API_KEY='sk-ant-...'\n"
                    "  export OPENAI_API_KEY='sk-...'\n"
                    "  export OPENROUTER_API_KEY='sk-or-...'\n\n"
                    "Or use --mode=mock for offline testing.\n"
                    + "=" * 60
                )

            if not self.model_name:
                self.model_name = {
                    "anthropic": "claude-3-5-sonnet-20241022",
                    "openai": "gpt-4o",
                    "openrouter": "google/gemini-2.5-flash"
                }.get(self.provider)

            logger.info(
                f"LLM Client initialized: mode=live, provider={self.provider}, "
                f"model={self.model_name}"
            )
        else:
            logger.info("LLM Client initialized: mode=mock (offline, rule-based responses)")

    def generate_completion(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        max_retries: int = 5,
        base_delay: float = 1.0,
        multiplier: float = 2.0
    ) -> str:
        """
        Generate a completion from the LLM.

        In mock mode, returns rule-based responses keyed on function names.
        In live mode, calls the configured API with retry-on-rate-limit.
        """
        if self.mode == "mock":
            return self._generate_mock_response(prompt)

        # Live mode — use requests library
        try:
            import requests
        except ImportError:
            raise ConfigurationError(
                "The 'requests' library is required for live mode. "
                "Install it with: pip install requests"
            )

        url, headers, payload = self._build_request(prompt, system_instruction)

        attempt = 0
        while attempt < max_retries:
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=60)

                if response.status_code == 429:
                    attempt += 1
                    delay = base_delay * (multiplier ** (attempt - 1))
                    logger.warning(
                        f"HTTP 429 Rate Limited. Retrying {attempt}/{max_retries} "
                        f"in {delay:.2f}s..."
                    )
                    time.sleep(delay)
                    continue

                response.raise_for_status()
                return self._parse_response(response.json())

            except Exception as e:
                attempt += 1
                if attempt >= max_retries:
                    logger.error(f"LLM API call failed after {max_retries} attempts: {e}")
                    raise
                delay = base_delay * (multiplier ** (attempt - 1))
                logger.warning(
                    f"LLM API error: {e}. Retrying {attempt}/{max_retries} "
                    f"in {delay:.2f}s..."
                )
                time.sleep(delay)

        raise RuntimeError("Failed to get response from LLM API (max retries reached).")

    def _build_request(self, prompt: str, system_instruction: Optional[str]):
        """Build the HTTP request for the configured provider."""
        if self.provider == "anthropic":
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": self.anthropic_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            messages = [{"role": "user", "content": prompt}]
            payload = {
                "model": self.model_name,
                "max_tokens": 4096,
                "messages": messages
            }
            if system_instruction:
                payload["system"] = system_instruction
            return url, headers, payload

        elif self.provider == "openai":
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.openai_key}",
                "Content-Type": "application/json"
            }
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})
            payload = {
                "model": self.model_name,
                "messages": messages,
                "temperature": 0.2
            }
            return url, headers, payload

        elif self.provider == "openrouter":
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.openrouter_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/nagarjunak-pixel/codexforge-tdd-mvp-v2",
                "X-Title": "CodexForge TDD"
            }
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})
            payload = {
                "model": self.model_name,
                "messages": messages,
                "temperature": 0.2
            }
            return url, headers, payload

        raise ConfigurationError(f"Unknown provider: {self.provider}")

    def _parse_response(self, data: dict) -> str:
        """Parse the API response based on provider."""
        if self.provider == "anthropic":
            return data["content"][0]["text"]
        elif self.provider in ("openai", "openrouter"):
            return data["choices"][0]["message"]["content"]
        raise ConfigurationError(f"Cannot parse response for provider: {self.provider}")

    def _generate_mock_response(self, prompt: str) -> str:
        """
        Rule-based mock response generator.

        Supports 3 diverse examples:
        1. buggy_divide.py — division by zero
        2. buggy_parser.py — CSV parsing with quoted fields
        3. buggy_dedup.py — list deduplication preserving order
        """
        prompt_lower = prompt.lower()

        # Determine intent using specific phrases from the orchestrator's prompts.
        # IMPORTANT: Simple keyword matching (e.g., "fix") fails because task
        # descriptions like "Fix the divide function..." also contain "fix".
        # Instead, match on unique phrases that only appear in one prompt type.
        is_repair = ("please fix/modify the code" in prompt_lower
                     or "so that the test passes" in prompt_lower
                     or "when we executed the test suite, it failed" in prompt_lower)
        is_test_gen = ("write a failing pytest test function" in prompt_lower
                       or "write only a valid python test" in prompt_lower)

        # ─── Example 1: Division by zero ───────────────────────────
        if "buggy_divide" in prompt_lower or "divide" in prompt_lower:
            if is_repair:
                return '''```python
def divide(a, b):
    """Divide a by b. Returns 0 if b is zero."""
    if b == 0:
        return 0
    return a / b
```'''
            if is_test_gen:
                return '''```python
import pytest
from buggy_divide import divide

def test_divide_normal():
    assert divide(10, 2) == 5.0

def test_divide_by_zero_returns_zero():
    """Division by zero should return 0, not raise ZeroDivisionError."""
    assert divide(10, 0) == 0

def test_divide_negative():
    assert divide(-6, 3) == -2.0
```'''

        # ─── Example 2: CSV parser with quoted fields ──────────────
        if "buggy_parser" in prompt_lower or "parse_csv" in prompt_lower or "csv" in prompt_lower:
            if is_repair:
                return '''```python
def parse_csv_line(line):
    """Parse a single CSV line, correctly handling quoted fields."""
    fields = []
    current = []
    in_quotes = False
    i = 0

    while i < len(line):
        char = line[i]

        if char == '"':
            if in_quotes and i + 1 < len(line) and line[i + 1] == '"':
                # Escaped quote inside quoted field
                current.append('"')
                i += 2
                continue
            else:
                in_quotes = not in_quotes
                i += 1
                continue

        if char == ',' and not in_quotes:
            fields.append(''.join(current))
            current = []
            i += 1
            continue

        current.append(char)
        i += 1

    fields.append(''.join(current))
    return fields
```'''
            if is_test_gen:
                return '''```python
import pytest
from buggy_parser import parse_csv_line

def test_simple_fields():
    assert parse_csv_line("a,b,c") == ["a", "b", "c"]

def test_quoted_field_with_comma():
    """Quoted fields containing commas should be kept intact."""
    assert parse_csv_line('a,"hello, world",c') == ["a", "hello, world", "c"]

def test_empty_fields():
    assert parse_csv_line("a,,c") == ["a", "", "c"]

def test_quoted_field_with_quotes():
    assert parse_csv_line('a,"say ""hi""",c') == ["a", 'say "hi"', "c"]
```'''

        # ─── Example 3: List deduplication preserving order ────────
        if "buggy_dedup" in prompt_lower or "deduplicate" in prompt_lower or "dedup" in prompt_lower:
            if is_repair:
                return '''```python
def deduplicate(items):
    """Remove duplicates from a list while preserving insertion order."""
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
```'''
            if is_test_gen:
                return '''```python
import pytest
from buggy_dedup import deduplicate

def test_basic_dedup():
    assert deduplicate([1, 2, 3, 2, 1]) == [1, 2, 3]

def test_preserves_insertion_order():
    """Must preserve the order of first occurrence."""
    result = deduplicate([3, 1, 4, 1, 5, 9, 2, 6, 5, 3])
    assert result == [3, 1, 4, 5, 9, 2, 6]

def test_empty_list():
    assert deduplicate([]) == []

def test_all_duplicates():
    assert deduplicate([7, 7, 7]) == [7]

def test_strings():
    assert deduplicate(["b", "a", "b", "c", "a"]) == ["b", "a", "c"]
```'''

        # ─── Fallback ─────────────────────────────────────────────
        logger.warning(
            f"Mock: No specific handler matched for prompt. "
            f"Returning generic response."
        )
        return (
            "```python\n"
            "# Mock response: No specific handler matched the prompt.\n"
            "# In live mode, the LLM would generate a real response here.\n"
            "pass\n"
            "```"
        )
