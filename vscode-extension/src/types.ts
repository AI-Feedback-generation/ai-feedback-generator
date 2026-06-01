/**
 * Type definitions for messages between VS Code extension and backend.
 * These mirror the Python types in backend/types/messages.py
 */

export enum MessageType {
    // From VS Code to Backend
    CONTEXT_UPDATE = 'context_update',
    CONTEXT_REQUEST = 'context_request',
    FEEDBACK_INTERACTION = 'feedback_interaction',

    // From Backend to VS Code
    FEEDBACK_DELIVERY = 'feedback_delivery',
    STATUS_UPDATE = 'status_update',
    ERROR = 'error',

    // Bidirectional
    PING = 'ping',
    PONG = 'pong',
    CONFIG_UPDATE = 'config_update',
}

export enum SystemStatus {
    INITIALIZING = 'initializing',
    READY = 'ready',
    RUNNING = 'running',
    STOPPED = 'stopped',
    ERROR = 'error',
    DISCONNECTED = 'disconnected',
}

export enum FeedbackType {
    HINT = 'hint',
    SUGGESTION = 'suggestion',
    WARNING = 'warning',
    EXPLANATION = 'explanation',
    SIMPLIFICATION = 'simplification',
}

export enum FeedbackPriority {
    LOW = 'low',
    MEDIUM = 'medium',
    HIGH = 'high',
    CRITICAL = 'critical',
}

export interface CodePosition {
    line: number;
    character: number;
}

export interface CodeRange {
    start: CodePosition;
    end: CodePosition;
    content?: string;
}

export interface DiagnosticInfo {
    message: string;
    severity: string;
    range: CodeRange;
    source?: string;
    code?: string;
}

export interface CodeContext {
    file_path: string;
    file_content?: string;
    language_id: string;
    cursor_position: CodePosition;
    selection?: CodeRange;
    visible_range?: CodeRange;
    diagnostics: DiagnosticInfo[];
    workspace_folder?: string;
    timestamp: number;
    metadata?: Record<string, unknown>;
}

export interface FeedbackMetadata {
    generated_at: number;
    generation_time_ms: number;
    cached: boolean;
    feedback_id: string;
    model_used?: string;
    cache_key?: string;
    session_id?: string;
    extra?: Record<string, unknown>;
}

export interface FeedbackItem {
    title: string;
    message: string;
    feedback_type: FeedbackType;
    priority: FeedbackPriority;
    code_range?: CodeRange;
    confidence: number;
    dismissible: boolean;
    actionable: boolean;
    action_label?: string;
    metadata: FeedbackMetadata;
}

export type InteractionType =
    | 'presented'
    | 'accepted'
    | 'rejected'
    | 'highlighted'
    | 'dismissed'
    | 'done';

export interface FeedbackInteraction {
    feedback_id: string;
    interaction_type: InteractionType;
    timestamp: number;
    metadata?: Record<string, unknown>;
}

export interface WebSocketMessage {
    type: MessageType;
    timestamp: number;
    payload: Record<string, unknown>;
    message_id?: string;
}

export interface FeedbackDeliveryPayload {
    items: FeedbackItem[];
    request_id?: string;
    triggered_by: string;
}

export interface SystemStatusMessage {
    status: SystemStatus;
    timestamp: number;
    feedback_generated: number;
    feedback_cooldown_left_s: number;
    llm_model?: string;
    error_message?: string;
}

export interface ContextRequestPayload {
    request_id: string;
    include_file_content: boolean;
    include_diagnostics: boolean;
    include_visible_range: boolean;
    active_file_only: boolean;
}
