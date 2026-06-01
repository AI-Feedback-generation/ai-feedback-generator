import { useState } from "react";
import type { SystemStatus } from "../types";

interface StatusPanelProps {
    status: SystemStatus;
}

export function StatusPanel({ status }: StatusPanelProps) {
    const [toggled, setToggled] = useState(true);

    return (
        <div className="section">
            <div
                className="section-title"
                style={{
                    display: "flex",
                    justifyContent: "space-between"
                }}
            >
                <span>System Status</span>
                <button className="btn small secondary toggle-btn" onClick={() => setToggled(!toggled)}>
                    {toggled ? "Hide" : "Show"}
                </button>
            </div>
            {toggled && (
                <div className="status-info">
                    <span className="label">Status</span>
                    <span className="value">{status.status}</span>

                    <span className="label">Feedback Generated</span>
                    <span className="value">{status.feedback_generated}</span>

                    <span className="label">Cooldown</span>
                    <span className="value">{status.feedback_cooldown_left_s || 0}s</span>

                    {status.llm_model && (
                        <>
                            <span className="label">LLM Model</span>
                            <span className="value">{status.llm_model}</span>
                        </>
                    )}
                </div>
            )}
        </div>
    );
}
