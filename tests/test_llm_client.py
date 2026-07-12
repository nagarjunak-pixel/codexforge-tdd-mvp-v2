"""Unit tests for router/llm_client.py"""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from router.llm_client import LLMClient, ConfigurationError


class TestLLMClientMockMode:
    """Tests for mock mode — no API key required."""

    def test_init_mock_mode(self):
        client = LLMClient(mode="mock")
        assert client.mode == "mock"

    def test_mock_divide_test_gen(self):
        """Test generation prompt should return pytest code."""
        client = LLMClient(mode="mock")
        response = client.generate_completion(
            "Write a failing pytest test function for buggy_divide.py"
        )
        assert "def test_" in response
        assert "from buggy_divide import divide" in response
        assert "divide(10, 0)" in response

    def test_mock_divide_repair(self):
        """Repair prompt should return fixed function code."""
        client = LLMClient(mode="mock")
        response = client.generate_completion(
            "Please fix/modify the code in buggy_divide.py so that the test passes."
        )
        assert "def divide" in response
        assert "if b == 0" in response
        assert "return 0" in response
        # Must NOT contain test code
        assert "def test_" not in response

    def test_mock_parser_test_gen(self):
        client = LLMClient(mode="mock")
        response = client.generate_completion(
            "Write a failing pytest test function for buggy_parser.py with parse_csv"
        )
        assert "def test_" in response
        assert "from buggy_parser import parse_csv_line" in response

    def test_mock_parser_repair(self):
        client = LLMClient(mode="mock")
        response = client.generate_completion(
            "Please fix/modify the code in buggy_parser.py so that the test passes. csv"
        )
        assert "def parse_csv_line" in response
        assert "in_quotes" in response

    def test_mock_dedup_test_gen(self):
        client = LLMClient(mode="mock")
        response = client.generate_completion(
            "Write a failing pytest test function for buggy_dedup.py with deduplicate"
        )
        assert "def test_" in response
        assert "from buggy_dedup import deduplicate" in response

    def test_mock_dedup_repair(self):
        client = LLMClient(mode="mock")
        response = client.generate_completion(
            "Please fix/modify the code in buggy_dedup.py so that the test passes. dedup"
        )
        assert "def deduplicate" in response
        assert "seen = set()" in response

    def test_mock_fallback(self):
        """Unrecognized prompt should return generic mock."""
        client = LLMClient(mode="mock")
        response = client.generate_completion("random unrelated prompt")
        assert "Mock response" in response or "pass" in response


class TestLLMClientLiveMode:
    """Tests for live mode — validates configuration errors."""

    def test_live_mode_no_key_raises(self):
        """Live mode without API key must raise ConfigurationError."""
        # Clear any existing keys
        old_anthropic = os.environ.pop("ANTHROPIC_API_KEY", None)
        old_openai = os.environ.pop("OPENAI_API_KEY", None)
        try:
            with pytest.raises(ConfigurationError, match="API key"):
                LLMClient(mode="live")
        finally:
            # Restore keys if they existed
            if old_anthropic:
                os.environ["ANTHROPIC_API_KEY"] = old_anthropic
            if old_openai:
                os.environ["OPENAI_API_KEY"] = old_openai

    def test_invalid_mode_raises(self):
        """Invalid mode must raise ConfigurationError."""
        with pytest.raises(ConfigurationError, match="Must be 'live' or 'mock'"):
            LLMClient(mode="invalid")


class TestCodeBlockExtraction:
    """Tests for the extract_code_block utility used by orchestrator."""

    def test_extract_python_block(self):
        client = LLMClient(mode="mock")
        text = '```python\ndef foo():\n    return 42\n```'
        result = client._generate_mock_response.__func__  # just test extraction logic
        # Use the orchestrator's extraction directly
        from engine.tdd_orchestrator import TDDOrchestrator
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            orch = TDDOrchestrator(td, "test.py", "test_test.py", mode="mock")
            assert orch.extract_code_block(text) == "def foo():\n    return 42"

    def test_extract_plain_text(self):
        """Without code fences, return stripped text."""
        from engine.tdd_orchestrator import TDDOrchestrator
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            orch = TDDOrchestrator(td, "test.py", "test_test.py", mode="mock")
            assert orch.extract_code_block("just plain code") == "just plain code"
