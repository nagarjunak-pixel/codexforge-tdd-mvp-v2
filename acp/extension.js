// CodexForge TDD — VS Code Extension
// Sends buffer diffs via JSON-RPC to the Python ACP server on localhost:9120.

const vscode = require('vscode');
const net = require('net');

/** @type {Map<string, string>} Track last-known content per document URI */
const lastKnownContent = new Map();

/**
 * Sends a JSON-RPC 2.0 payload to the ACP Python server over TCP.
 * @param {string} host
 * @param {number} port
 * @param {object} payload - JSON-RPC 2.0 object
 * @returns {Promise<string>} - Response from server
 */
function sendJsonRpc(host, port, payload) {
    return new Promise((resolve, reject) => {
        const client = new net.Socket();
        const data = JSON.stringify(payload);
        let response = '';

        client.connect(port, host, () => {
            // Send length-prefixed message: 4-byte big-endian length + JSON
            const lengthBuffer = Buffer.alloc(4);
            lengthBuffer.writeUInt32BE(Buffer.byteLength(data, 'utf8'), 0);
            client.write(lengthBuffer);
            client.write(data, 'utf8');
        });

        client.on('data', (chunk) => {
            response += chunk.toString('utf8');
        });

        client.on('end', () => {
            resolve(response);
        });

        client.on('error', (err) => {
            reject(err);
        });

        // Timeout after 10 seconds
        client.setTimeout(10000, () => {
            client.destroy();
            reject(new Error('Connection to ACP server timed out'));
        });
    });
}

/**
 * Generates a textDocument/didChange JSON-RPC payload.
 * @param {string} uri - Document URI
 * @param {string} oldText - Previous content
 * @param {string} newText - Current content
 * @param {number} version - Document version
 * @returns {object} JSON-RPC 2.0 payload
 */
function createDidChangePayload(uri, oldText, newText, version) {
    return {
        jsonrpc: '2.0',
        method: 'textDocument/didChange',
        id: Date.now(),
        params: {
            textDocument: {
                uri: uri,
                version: version
            },
            contentChanges: [
                {
                    // Full document replacement for robustness
                    text: newText
                }
            ],
            // Include old text so server can compute diffs if needed
            _oldText: oldText
        }
    };
}

/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {
    console.log('CodexForge TDD extension activated');

    const config = vscode.workspace.getConfiguration('codexforge');
    const host = config.get('agentHost', 'localhost');
    const port = config.get('agentPort', 9120);

    // Command: Send current buffer to agent
    const sendBufferCmd = vscode.commands.registerCommand('codexforge.sendBuffer', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showWarningMessage('CodexForge: No active editor found.');
            return;
        }

        const doc = editor.document;
        const uri = doc.uri.toString();
        const currentText = doc.getText();
        const oldText = lastKnownContent.get(uri) || '';
        const version = doc.version;

        if (currentText === oldText) {
            vscode.window.showInformationMessage('CodexForge: No changes detected in buffer.');
            return;
        }

        const payload = createDidChangePayload(uri, oldText, currentText, version);

        try {
            const response = await sendJsonRpc(host, port, payload);
            lastKnownContent.set(uri, currentText);
            vscode.window.showInformationMessage(`CodexForge: Buffer sent successfully. Server: ${response || 'ack'}`);
        } catch (err) {
            vscode.window.showErrorMessage(
                `CodexForge: Failed to send buffer to agent at ${host}:${port}. ` +
                `Is the ACP server running? Error: ${err.message}`
            );
        }
    });

    // Command: Start TDD loop
    const startTddCmd = vscode.commands.registerCommand('codexforge.startTDD', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showWarningMessage('CodexForge: No active editor found.');
            return;
        }

        const task = await vscode.window.showInputBox({
            prompt: 'Describe the bug or requirement for the TDD loop',
            placeHolder: 'e.g., Fix division by zero in calculate.py'
        });

        if (!task) {
            return; // User cancelled
        }

        const doc = editor.document;
        const uri = doc.uri.toString();
        const currentText = doc.getText();

        const payload = {
            jsonrpc: '2.0',
            method: 'codexforge/startTDD',
            id: Date.now(),
            params: {
                textDocument: {
                    uri: uri
                },
                task: task,
                sourceCode: currentText
            }
        };

        try {
            vscode.window.showInformationMessage('CodexForge: Starting TDD loop...');
            const response = await sendJsonRpc(host, port, payload);
            vscode.window.showInformationMessage(`CodexForge: TDD loop result: ${response || 'completed'}`);
        } catch (err) {
            vscode.window.showErrorMessage(
                `CodexForge: Failed to start TDD loop. Error: ${err.message}`
            );
        }
    });

    // Track document changes for diff computation
    const changeListener = vscode.workspace.onDidOpenTextDocument((doc) => {
        lastKnownContent.set(doc.uri.toString(), doc.getText());
    });

    // Initialize tracking for already-open documents
    if (vscode.window.activeTextEditor) {
        const doc = vscode.window.activeTextEditor.document;
        lastKnownContent.set(doc.uri.toString(), doc.getText());
    }

    context.subscriptions.push(sendBufferCmd, startTddCmd, changeListener);
}

function deactivate() {
    lastKnownContent.clear();
    console.log('CodexForge TDD extension deactivated');
}

module.exports = {
    activate,
    deactivate
};
