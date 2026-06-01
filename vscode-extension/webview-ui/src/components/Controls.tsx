import { useState } from "react";

interface ControlsProps {
  isConnected: boolean;
  onConnect: () => void;
  onDisconnect: () => void;
  onClearFeedback: () => void;
}

export function Controls({
  isConnected,
  onConnect,
  onDisconnect,
  onClearFeedback,
}: ControlsProps) {
  const [toggled, setToggled] = useState(false);

  return (
    <div className="section">
      <div className="section-title"
        style={{
          display: "flex",
          justifyContent: "space-between"
        }}
      >
        <span>Controls</span>
        <button className="btn small secondary toggle-btn" onClick={() => setToggled(!toggled)}>
          {toggled ? "Hide" : "Show"}
        </button>
      </div>
      {toggled && (
        <div className="controls">
          {!isConnected ? (
            <button className="btn" onClick={onConnect}>
              Connect Backend
            </button>
          ) : (
            <button className="btn secondary" onClick={onDisconnect}>
              Disconnect
            </button>
          )}

          <button className="btn secondary" onClick={onClearFeedback}>
            Clear Feedback
          </button>
        </div>
      )}
    </div>
  );
}
