/**
 * AI Feedback Generator Extension
 *
 * Main entry point for the VS Code extension.
 * Handles extension activation, command registration, and lifecycle management.
 */
import * as vscode from 'vscode';
import { WebSocketClient } from './websocket-client';
import { ContextCollector } from './context-collector';
import { FeedbackRenderer } from './feedback-renderer';
import { StatusBarManager } from './status-bar';
import { FeedbackViewProvider } from './webview-provider';
import {
    MessageType,
    FeedbackDeliveryPayload,
    SystemStatus,
    FeedbackInteraction,
} from './types';
import { isStatusUpdatePayload } from './utils/typeguard';
import { fetchStatus } from './api';

let wsClient: WebSocketClient | null = null;
let contextCollector: ContextCollector | null = null;
let feedbackRenderer: FeedbackRenderer | null = null;
let statusBar: StatusBarManager | null = null;
let webviewProvider: FeedbackViewProvider | null = null;

// Debounce timer for context updates
let contextUpdateTimer: NodeJS.Timeout | null = null;
const CONTEXT_UPDATE_DEBOUNCE_MS = 500;

// Configuration for backend connection
const config = vscode.workspace.getConfiguration('eyeTrackingDebugger');
const host = config.get<string>('backendHost') || 'localhost';
const port = config.get<number>('apiPort') || 8080;

/**
 * Extension activation.
 */
export async function activate(
    context: vscode.ExtensionContext,
): Promise<void> {
    console.log('AI Feedback Generator extension is now active');

    initializeComponents(context);
    registerCommands(context);
    setupEventListeners(context);

    if (config.get<boolean>('autoConnectBackend')) {
        await connectToBackend();
    }

    await refreshStatus();
}

/**
 * Extension deactivation.
 */
export async function deactivate(): Promise<void> {
    wsClient?.disconnect();
    feedbackRenderer?.dispose();
    statusBar?.dispose();
}

/**
 * Initialize all extension components.
 */
function initializeComponents(context: vscode.ExtensionContext): void {
    const config = vscode.workspace.getConfiguration('eyeTrackingDebugger');
    const host = config.get<string>('backendHost') || 'localhost';
    const port = config.get<number>('websocketPort') || 8765;

    wsClient = new WebSocketClient(host, port);

    webviewProvider = new FeedbackViewProvider(context.extensionUri);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(
            FeedbackViewProvider.viewType,
            webviewProvider,
        ),
    );

    webviewProvider.setCallbacks({
        onConnect: connectToBackend,
        onDisconnect: disconnectFromBackend,
        onClearFeedback: clearFeedback,
        onTriggerFeedback: triggerFeedbackSend,
        onFeedbackInteraction: (feedbackId, interactionType) => {
            handleFeedbackInteraction({
                feedback_id: feedbackId,
                interaction_type: interactionType,
                timestamp: Math.floor(Date.now() / 1000),
            });
        },
        onSetCooldown: setCooldown,
    });

    contextCollector = new ContextCollector();
    feedbackRenderer = new FeedbackRenderer(context);
    statusBar = new StatusBarManager(context);

    feedbackRenderer.setInteractionCallback((interaction) => {
        handleFeedbackInteraction(interaction);
    });

    wsClient.onConnectionChange((connected: boolean) => {
        statusBar?.setConnected(connected);
        webviewProvider?.updateConnectionStatus(connected);
    });

    setupMessageHandlers();
}

async function refreshStatus(): Promise<void> {
    try {
        const statusPayload = await fetchStatus(host, port);
        if (isStatusUpdatePayload(statusPayload)) {
            statusBar?.setStatus(statusPayload);
            webviewProvider?.updateStatus(statusPayload);
        } else {
            console.warn(
                '/status response did not match expected shape',
                statusPayload,
            );
        }
    } catch (error) {
        console.error('Failed to fetch status from backend:', error);
        statusBar?.setConnected(false);
    }
}

/**
 * Register extension commands.
 */
function registerCommands(context: vscode.ExtensionContext): void {
    context.subscriptions.push(
        vscode.commands.registerCommand(
            'eyeTrackingDebugger.connect',
            connectToBackend,
        ),
    );

    context.subscriptions.push(
        vscode.commands.registerCommand(
            'eyeTrackingDebugger.disconnect',
            disconnectFromBackend,
        ),
    );

    context.subscriptions.push(
        vscode.commands.registerCommand(
            'eyeTrackingDebugger.showStatus',
            showStatus,
        ),
    );

    context.subscriptions.push(
        vscode.commands.registerCommand(
            'eyeTrackingDebugger.clearFeedback',
            clearFeedback,
        ),
    );

    context.subscriptions.push(
        vscode.commands.registerCommand(
            'eyeTrackingDebugger.triggerFeedbackSend',
            triggerFeedbackSend,
        ),
    );

    context.subscriptions.push(
        vscode.commands.registerCommand(
            'eyeTrackingDebugger.setCooldown',
            setCooldown,
        ),
    );
}

/**
 * Set up event listeners for editor changes.
 */
function setupEventListeners(context: vscode.ExtensionContext): void {
    context.subscriptions.push(
        vscode.window.onDidChangeActiveTextEditor(onActiveEditorChanged),
    );

    context.subscriptions.push(
        vscode.workspace.onDidChangeTextDocument(onDocumentChanged),
    );

    context.subscriptions.push(
        vscode.window.onDidChangeTextEditorSelection(onSelectionChanged),
    );

    context.subscriptions.push(
        vscode.workspace.onDidChangeConfiguration(onConfigurationChanged),
    );
}

/**
 * Set up WebSocket message handlers.
 */
function setupMessageHandlers(): void {
    if (!wsClient) return;

    wsClient.onMessage(MessageType.FEEDBACK_DELIVERY, handleFeedbackDelivery);
    wsClient.onMessage(MessageType.STATUS_UPDATE, handleStatusUpdate);
    wsClient.onMessage(MessageType.CONTEXT_REQUEST, handleContextRequest);
    wsClient.onMessage(MessageType.ERROR, handleError);
}

// --- Command Handlers ---

async function connectToBackend(): Promise<void> {
    if (!wsClient) return;

    const connected = await wsClient.connect();
    if (connected) {
        vscode.window.showInformationMessage(
            'Connected to AI Feedback Generator backend',
        );
        statusBar?.setConnected(true);
        webviewProvider?.updateConnectionStatus(true);
        sendContextUpdate();
        refreshStatus();
    } else {
        vscode.window.showErrorMessage(
            'Failed to connect to AI Feedback Generator backend',
        );
        webviewProvider?.updateConnectionStatus(false);
    }
}

async function disconnectFromBackend(): Promise<void> {
    const result = await vscode.window.showInformationMessage(
        'Do you want to disconnect from the AI Feedback Generator backend?',
        { modal: true },
        'Yes',
        'No',
    );

    if (result !== 'Yes') {
        return;
    }

    wsClient?.disconnect();
    statusBar?.setConnected(false);
    webviewProvider?.updateConnectionStatus(false);
    vscode.window.showInformationMessage(
        'Disconnected from AI Feedback Generator backend',
    );
}

async function setCooldown(cooldownSeconds: number): Promise<void> {
    if (!cooldownSeconds) {
        const input = await vscode.window.showInputBox({
            prompt: 'Enter cooldown duration in seconds (0 to disable)',
            placeHolder: 'e.g., 60 for 1 minute',
            validateInput: (value) => {
                const num = Number(value);
                if (isNaN(num) || num < 0) {
                    return 'Please enter a valid non-negative number';
                }
                return null;
            },
        });
        if (input === undefined) return;
        cooldownSeconds = Number(input);
    }

    try {
        await fetch(`http://${host}:${port}/cooldown`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cooldown_seconds: cooldownSeconds }),
        });
    } catch (error) {
        console.error('Failed to set cooldown:', error);
    }
}

async function showStatus(): Promise<void> {
    if (statusBar) {
        await statusBar.showStatusDetails();
    } else {
        vscode.window.showInformationMessage('No status available');
    }
}

function clearFeedback(): void {
    feedbackRenderer?.clearAll();
    webviewProvider?.clearFeedback();
    vscode.window.showInformationMessage('Feedback cleared');
}

async function triggerFeedbackSend(): Promise<void> {
    try {
        await fetch(`http://${host}:${port}/feedback/manual_send`, {
            method: 'GET',
        });
    } catch (error) {
        console.error('Failed to trigger manual feedback send:', error);
    }
}

// --- Event Handlers ---

function onActiveEditorChanged(editor: vscode.TextEditor | undefined): void {
    if (editor) {
        sendContextUpdate();
        refreshStatus();
    }
}

function onDocumentChanged(event: vscode.TextDocumentChangeEvent): void {
    const activeEditor = vscode.window.activeTextEditor;
    if (activeEditor && event.document === activeEditor.document) {
        scheduleContextUpdate();
        refreshStatus();
    }
}

function onSelectionChanged(
    event: vscode.TextEditorSelectionChangeEvent,
): void {
    console.log(
        `Selection changed in: ${event.textEditor.document.uri.toString()}`,
    );
    scheduleContextUpdate();
    refreshStatus();
}

function scheduleContextUpdate(): void {
    if (contextUpdateTimer) {
        clearTimeout(contextUpdateTimer);
    }
    contextUpdateTimer = setTimeout(() => {
        sendContextUpdate();
    }, CONTEXT_UPDATE_DEBOUNCE_MS);
}

function sendContextUpdate(): void {
    if (!wsClient?.isConnected()) {
        return;
    }

    const context = contextCollector?.collectContext();
    if (context) {
        wsClient.sendContextUpdate(context);
    }
}

function onConfigurationChanged(event: vscode.ConfigurationChangeEvent): void {
    if (event.affectsConfiguration('eyeTrackingDebugger')) {
        updateConfiguration();
    }
}

function updateConfiguration(): void {
    wsClient?.updateSettings(host, port);
}

// --- Message Handlers ---

function handleFeedbackDelivery(message: {
    payload: Record<string, unknown>;
}): void {
    const payload = message.payload as unknown as FeedbackDeliveryPayload;
    feedbackRenderer?.addFeedback(payload.items);
    webviewProvider?.updateFeedback(payload.items);
}

function handleStatusUpdate(message: {
    payload: Record<string, unknown>;
}): void {
    const payloadUnknown = message.payload;

    if (!isStatusUpdatePayload(payloadUnknown)) {
        console.warn(
            'STATUS_UPDATE payload did not match StatusUpdatePayload shape',
            payloadUnknown,
        );
        return;
    }

    statusBar?.setStatus(payloadUnknown);
    webviewProvider?.updateStatus(payloadUnknown);

    if (payloadUnknown.status === SystemStatus.ERROR && payloadUnknown.error_message) {
        console.error('Backend error:', payloadUnknown.error_message);
        vscode.window.showErrorMessage(
            `AI Feedback Generator Error: ${payloadUnknown.error_message}`,
        );
    }
}

function handleContextRequest(_message: {
    payload: Record<string, unknown>;
}): void {
    const context = contextCollector?.collectContext();
    if (context && wsClient) {
        wsClient.sendContextUpdate(context);
    }
}

function handleError(message: { payload: Record<string, unknown> }): void {
    const errorMessage =
        (message.payload['message'] as string) || 'Unknown error';
    vscode.window.showErrorMessage(`AI Feedback Error: ${errorMessage}`);
}

async function handleFeedbackInteraction(
    feedbackInteraction: FeedbackInteraction,
) {
    if (
        feedbackInteraction.interaction_type === 'dismissed' ||
        feedbackInteraction.interaction_type === 'done' ||
        feedbackInteraction.interaction_type === 'rejected'
    ) {
        webviewProvider?.removeFeedback(feedbackInteraction.feedback_id);
    }

    if (feedbackInteraction.interaction_type === 'highlighted') {
        feedbackRenderer?.highlightFeedback(feedbackInteraction.feedback_id);
    }

    if (feedbackInteraction.interaction_type === 'dismissed') {
        feedbackRenderer?.removeHighlightById(feedbackInteraction.feedback_id);
    }

    if (feedbackInteraction.interaction_type === 'done') {
        feedbackRenderer?.removeHighlightById(feedbackInteraction.feedback_id);
    }

    try {
        await fetch(`http://${host}:${port}/feedback/interaction`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(feedbackInteraction),
        });
    } catch (error) {
        console.error('Failed to send feedback interaction:', error);
    }
}
