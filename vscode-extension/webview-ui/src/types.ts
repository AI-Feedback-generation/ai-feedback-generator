/**
 * Types shared between webview and extension.
 * These mirror the extension types for use in React.
 */

export enum FeedbackType {
  HINT = "hint",
  SUGGESTION = "suggestion",
  WARNING = "warning",
  EXPLANATION = "explanation",
  SIMPLIFICATION = "simplification",
}

export enum FeedbackPriority {
  LOW = "low",
  MEDIUM = "medium",
  HIGH = "high",
  CRITICAL = "critical",
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
  | "presented"
  | "accepted"
  | "rejected"
  | "highlighted"
  | "dismissed"
  | "done";

export interface SystemStatus {
  status:
    | "initializing"
    | "ready"
    | "running"
    | "stopped"
    | "error"
    | "disconnected";
  timestamp: number;
  feedback_generated: number;
  feedback_cooldown_left_s: number;
  llm_model?: string;
  error_message?: string;
}
