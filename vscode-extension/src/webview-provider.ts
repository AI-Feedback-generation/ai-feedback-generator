/**
 * WebviewViewProvider for the AI Feedback Generator panel.
 */
import * as vscode from 'vscode';
import {
    FeedbackItem,
    SystemStatusMessage,
    InteractionType,
} from './types';

// Set to true during development to load from Vite dev server
const DEV_MODE = false;
const DEV_SERVER_URL = 'http://localhost:5173';

export class FeedbackViewProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'eyeTrackingDebugger.feedbackView';

    private _view?: vscode.WebviewView;
    private _extensionUri: vscode.Uri;

    // Callbacks for handling webview messages
    private _onConnect?: () => void;
    private _onDisconnect?: () => void;
    private _onClearFeedback?: () => void;
    private _onTriggerFeedback?: () => void;
    private _onFeedbackInteraction?: (
        feedbackId: string,
        interactionType: InteractionType,
    ) => void;
    private _onSetCooldown?: (cooldownSeconds: number) => void;

    constructor(extensionUri: vscode.Uri) {
        this._extensionUri = extensionUri;
    }

    public setCallbacks(callbacks: {
        onConnect?: () => void;
        onDisconnect?: () => void;
        onClearFeedback?: () => void;
        onTriggerFeedback?: () => void;
        onFeedbackInteraction?: (
            feedbackId: string,
            interactionType: InteractionType,
        ) => void;
        onSetCooldown?: (cooldownSeconds: number) => void;
    }): void {
        this._onConnect = callbacks.onConnect;
        this._onDisconnect = callbacks.onDisconnect;
        this._onClearFeedback = callbacks.onClearFeedback;
        this._onTriggerFeedback = callbacks.onTriggerFeedback;
        this._onFeedbackInteraction = callbacks.onFeedbackInteraction;
        this._onSetCooldown = callbacks.onSetCooldown;
    }

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        _context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken,
    ): void {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [
                vscode.Uri.joinPath(this._extensionUri, 'webview-ui', 'build'),
            ],
        };

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

        webviewView.webview.onDidReceiveMessage((message) => {
            this._handleWebviewMessage(message);
        });

        webviewView.onDidChangeVisibility(() => {
            if (webviewView.visible) {
                console.log('Webview became visible');
            }
        });
    }

    public updateConnectionStatus(connected: boolean): void {
        this._postMessage({
            type: 'connectionStatus',
            payload: { connected },
        });
    }

    public updateStatus(status: SystemStatusMessage): void {
        this._postMessage({
            type: 'statusUpdate',
            payload: status,
        });
    }

    public updateFeedback(items: FeedbackItem[]): void {
        this._postMessage({
            type: 'feedbackUpdate',
            payload: { items },
        });
    }

    public clearFeedback(): void {
        this._postMessage({
            type: 'clearFeedback',
            payload: {},
        });
    }

    public removeFeedback(feedbackId: string): void {
        this._postMessage({
            type: 'removeFeedback',
            payload: { feedbackId },
        });
    }

    private _handleWebviewMessage(message: {
        type: string;
        payload?: unknown;
    }): void {
        switch (message.type) {
            case 'ready':
                console.log('Webview ready, sending initial state');
                break;
            case 'connect':
                this._onConnect?.();
                break;
            case 'disconnect':
                this._onDisconnect?.();
                break;
            case 'clearFeedback':
                this._onClearFeedback?.();
                break;
            case 'triggerFeedback':
                this._onTriggerFeedback?.();
                break;
            case 'feedbackInteraction':
                const payload = message.payload as {
                    feedbackId: string;
                    interactionType: InteractionType;
                };
                this._onFeedbackInteraction?.(
                    payload.feedbackId,
                    payload.interactionType,
                );
                break;
            case 'setCooldown':
                const cooldownPayload = message.payload as { cooldownSeconds: number };
                this._onSetCooldown?.(cooldownPayload.cooldownSeconds);
                break;
            default:
                console.log('Unknown webview message:', message.type);
        }
    }

    private _postMessage(message: { type: string; payload: unknown }): void {
        if (this._view) {
            this._view.webview.postMessage(message);
        }
    }

    private _getHtmlForWebview(webview: vscode.Webview): string {
        const nonce = this._getNonce();

        if (DEV_MODE) {
            return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Feedback</title>
</head>
<body>
    <div id="root"></div>
    <script type="module">
        import RefreshRuntime from "${DEV_SERVER_URL}/@react-refresh"
        RefreshRuntime.injectIntoGlobalHook(window)
        window.$RefreshReg$ = () => {}
        window.$RefreshSig$ = () => (type) => type
        window.__vite_plugin_react_preamble_installed__ = true
    </script>
    <script type="module" src="${DEV_SERVER_URL}/src/main.tsx"></script>
</body>
</html>`;
        }

        const scriptUri = webview.asWebviewUri(
            vscode.Uri.joinPath(
                this._extensionUri,
                'webview-ui',
                'build',
                'assets',
                'main.js',
            ),
        );
        const styleUri = webview.asWebviewUri(
            vscode.Uri.joinPath(
                this._extensionUri,
                'webview-ui',
                'build',
                'assets',
                'main.css',
            ),
        );

        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}';">
    <link href="${styleUri}" rel="stylesheet">
    <title>AI Feedback</title>
</head>
<body>
    <div id="root"></div>
    <script type="module" nonce="${nonce}" src="${scriptUri}"></script>
</body>
</html>`;
    }

    private _getNonce(): string {
        let text = '';
        const possible =
            'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
        for (let i = 0; i < 32; i++) {
            text += possible.charAt(Math.floor(Math.random() * possible.length));
        }
        return text;
    }
}
