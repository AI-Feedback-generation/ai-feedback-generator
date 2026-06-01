import { SystemStatusMessage } from "../types";

export function isStatusUpdatePayload(x: unknown): x is SystemStatusMessage {
    if (!x || typeof x !== "object") return false;
    const o = x as Record<string, unknown>;

    if (typeof o.status !== "string") return false;
    if (typeof o.timestamp !== "number") return false;
    if (typeof o.operation_mode !== "string") return false;
    if (typeof o.feedback_generated !== "number") return false;

    if ("llm_model" in o && o.llm_model !== undefined && o.llm_model !== null && typeof o.llm_model !== "string") return false;
    if ("error_message" in o && o.error_message !== undefined && o.error_message !== null && typeof o.error_message !== "string") return false;

    return true;
}
