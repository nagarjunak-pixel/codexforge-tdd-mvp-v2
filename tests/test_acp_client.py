"""Unit tests for acp/acp_client.py"""

import os
import sys
import json
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from acp.acp_client import ACPClient


class TestACPClient:
    """Tests for the ACP client's payload generation and application."""

    def test_generate_did_change_payload(self):
        """Should produce a valid textDocument/didChange dict payload."""
        client = ACPClient("file:///test/file.py")
        old = "def foo():\n    return 1\n"
        new = "def foo():\n    return 42\n"
        payload = client.generate_did_change_payload(old, new)

        # Payload is a dict (not a JSON string)
        assert isinstance(payload, dict)
        assert payload["jsonrpc"] == "2.0"
        assert payload["method"] == "textDocument/didChange"
        assert "params" in payload
        assert payload["params"]["textDocument"]["uri"] == "file:///test/file.py"
        assert "contentChanges" in payload["params"]
        assert len(payload["params"]["contentChanges"]) > 0

    def test_apply_did_change_payload_full_replace(self):
        """Applying a full-document change should produce the new content."""
        client = ACPClient("file:///test.py")
        old = "old content"
        new = "new content"
        payload = client.generate_did_change_payload(old, new)

        result = ACPClient.apply_did_change_payload(payload, old)
        assert result == new

    def test_apply_did_change_no_change(self):
        """When old == new, applying changes should return the same content."""
        client = ACPClient("file:///test.py")
        content = "unchanged content"
        payload = client.generate_did_change_payload(content, content)

        result = ACPClient.apply_did_change_payload(payload, content)
        assert result == content

    def test_multiline_change(self):
        """Test with multiline content replacement."""
        client = ACPClient("file:///test.py")
        old = "line1\nline2\nline3\nline4\n"
        new = "line1\nmodified_line2\nnew_line3\nline4\n"
        payload = client.generate_did_change_payload(old, new)

        result = ACPClient.apply_did_change_payload(payload, old)
        assert result == new

    def test_payload_is_serializable(self):
        """Payload dict must be JSON-serializable."""
        client = ACPClient("file:///test.py")
        payload = client.generate_did_change_payload("a", "b")
        # Should not raise
        json_str = json.dumps(payload)
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)

    def test_uri_preserved(self):
        """Document URI should be correctly preserved in the payload."""
        uri = "file:///Users/test/project/main.py"
        client = ACPClient(uri)
        payload = client.generate_did_change_payload("x", "y")
        assert payload["params"]["textDocument"]["uri"] == uri
