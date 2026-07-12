"""
CodexForge ACP Client & Server — v2

Provides:
1. A TCP server (port 9120) that receives JSON-RPC payloads from the VS Code extension.
2. A programmatic Python client API for the TDD orchestrator to generate and apply diffs.

Protocol: Length-prefixed JSON-RPC 2.0 over TCP.
  - 4 bytes big-endian uint32 length prefix
  - followed by UTF-8 JSON payload
"""

import json
import struct
import socket
import threading
import logging
import difflib
from typing import Dict, Any, Optional, Callable

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ACPClient")

# Default ACP server port
DEFAULT_PORT = 9120
DEFAULT_HOST = "localhost"


class ACPClient:
    """Programmatic client for generating and applying textDocument/didChange payloads."""

    def __init__(self, uri: str):
        self.uri = uri
        self._version = 0

    def generate_did_change_payload(self, old_text: str, new_text: str) -> Dict[str, Any]:
        """
        Generates a JSON-RPC 2.0 textDocument/didChange payload.

        Supports both full-text replacement and range-based changes.
        For robustness in the MVP, we send full text with the old text
        included as metadata for server-side diff computation.
        """
        self._version += 1

        # Compute line-level diff for informational purposes
        old_lines = old_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)
        diff_ops = list(difflib.unified_diff(old_lines, new_lines, lineterm=""))

        return {
            "jsonrpc": "2.0",
            "method": "textDocument/didChange",
            "params": {
                "textDocument": {
                    "uri": self.uri,
                    "version": self._version
                },
                "contentChanges": [
                    {
                        "text": new_text
                    }
                ],
                # Metadata for server-side processing
                "_oldText": old_text,
                "_diffSummary": {
                    "linesAdded": sum(1 for op in diff_ops if op.startswith("+")),
                    "linesRemoved": sum(1 for op in diff_ops if op.startswith("-")),
                }
            }
        }

    @staticmethod
    def apply_did_change_payload(payload: Dict[str, Any], current_text: str) -> str:
        """
        Applies a JSON-RPC textDocument/didChange payload's changes to the current text buffer.

        Supports:
        - Full text replacement (no range specified)
        - Range-based changes (with start/end line/character positions)
        """
        params = payload.get("params", {})
        changes = params.get("contentChanges", [])

        for change in changes:
            if "range" in change:
                # Range-based change
                range_info = change["range"]
                start_line = range_info["start"]["line"]
                start_char = range_info["start"]["character"]
                end_line = range_info["end"]["line"]
                end_char = range_info["end"]["character"]

                lines = current_text.splitlines(keepends=True)

                # Build prefix (everything before the range)
                prefix = "".join(lines[:start_line])
                if start_line < len(lines):
                    prefix += lines[start_line][:start_char]

                # Build suffix (everything after the range)
                suffix = ""
                if end_line < len(lines):
                    suffix = lines[end_line][end_char:]
                suffix += "".join(lines[end_line + 1:])

                # Apply the change
                current_text = prefix + change.get("text", "") + suffix
            else:
                # Full text replacement
                current_text = change.get("text", "")

        return current_text


class ACPServer:
    """
    TCP server that receives JSON-RPC payloads from the VS Code extension.

    Listens on a configurable host:port and dispatches received payloads
    to registered handler callbacks.
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self._handlers: Dict[str, Callable] = {}
        self._server_socket: Optional[socket.socket] = None
        self._running = False

    def register_handler(self, method: str, handler: Callable):
        """Register a handler for a specific JSON-RPC method."""
        self._handlers[method] = handler
        logger.info(f"Registered handler for method: {method}")

    def _handle_client(self, client_socket: socket.socket, addr):
        """Handle a single client connection."""
        try:
            # Read 4-byte length prefix
            length_data = client_socket.recv(4)
            if len(length_data) < 4:
                logger.warning(f"Incomplete length prefix from {addr}")
                return

            msg_length = struct.unpack(">I", length_data)[0]

            # Read the full message
            data = b""
            while len(data) < msg_length:
                chunk = client_socket.recv(min(4096, msg_length - len(data)))
                if not chunk:
                    break
                data += chunk

            payload = json.loads(data.decode("utf-8"))
            method = payload.get("method", "")
            msg_id = payload.get("id")

            logger.info(f"Received JSON-RPC: method={method}, id={msg_id}")

            # Dispatch to handler
            if method in self._handlers:
                try:
                    result = self._handlers[method](payload)
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": result or {"status": "ok"}
                    }
                except Exception as e:
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {"code": -32000, "message": str(e)}
                    }
            else:
                logger.warning(f"No handler registered for method: {method}")
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                }

            # Send response
            resp_data = json.dumps(response).encode("utf-8")
            client_socket.sendall(resp_data)

        except Exception as e:
            logger.error(f"Error handling client {addr}: {e}")
        finally:
            client_socket.close()

    def start(self, blocking: bool = True):
        """Start the TCP server."""
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.host, self.port))
        self._server_socket.listen(5)
        self._running = True

        logger.info(f"ACP Server listening on {self.host}:{self.port}")

        if blocking:
            self._accept_loop()
        else:
            thread = threading.Thread(target=self._accept_loop, daemon=True)
            thread.start()

    def _accept_loop(self):
        """Accept incoming connections in a loop."""
        while self._running:
            try:
                self._server_socket.settimeout(1.0)
                try:
                    client_socket, addr = self._server_socket.accept()
                    logger.info(f"Connection from {addr}")
                    thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, addr),
                        daemon=True
                    )
                    thread.start()
                except socket.timeout:
                    continue
            except Exception as e:
                if self._running:
                    logger.error(f"Accept error: {e}")

    def stop(self):
        """Stop the TCP server."""
        self._running = False
        if self._server_socket:
            self._server_socket.close()
            logger.info("ACP Server stopped")


# CLI test
if __name__ == "__main__":
    # Test the client API
    client = ACPClient("file:///workspace/app.py")
    old = "def hello():\n    print('world')\n"
    new = "def hello():\n    print('hello world')\n"

    payload = client.generate_did_change_payload(old, new)
    print("Generated Payload:")
    print(json.dumps(payload, indent=2))

    applied = ACPClient.apply_did_change_payload(payload, old)
    print(f"\nApplied Text Match: {applied == new}")
    assert applied == new, "Full-text apply failed!"

    # Test range-based apply
    range_payload = {
        "params": {
            "contentChanges": [
                {
                    "range": {
                        "start": {"line": 1, "character": 10},
                        "end": {"line": 1, "character": 17}
                    },
                    "text": "'hello world'"
                }
            ]
        }
    }
    range_applied = ACPClient.apply_did_change_payload(range_payload, old)
    print(f"Range-based apply result:\n{range_applied}")

    print("\nAll ACP client tests passed!")
