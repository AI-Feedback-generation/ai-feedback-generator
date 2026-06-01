import { useState, useEffect, useRef } from "react";
import type { FeedbackItem, InteractionType } from "../types";

interface FeedbackListProps {
  items: FeedbackItem[];
  onInteraction: (feedbackId: string, interactionType: InteractionType) => void;
}

export function FeedbackList({ items, onInteraction }: FeedbackListProps) {
  if (items.length === 0) {
    return (
      <div className="empty-state">
        No feedback available. Start coding and feedback will appear here based on your activity.
      </div>
    );
  }

  return (
    <div className="feedback-list">
      {items.map((item) => (
        <FeedbackAlertCard
          key={item.metadata.feedback_id}
          item={item}
          onInteraction={(type) => onInteraction(item.metadata.feedback_id, type)}
        />
      ))}
    </div>
  );
}

interface FeedbackAlertCardProps {
  item: FeedbackItem;
  onInteraction: (type: InteractionType) => void;
}

function FeedbackAlertCard({ item, onInteraction }: FeedbackAlertCardProps) {
  const [phase, setPhase] = useState<"prompt" | "detail">("prompt");

  // Fire "presented" once on mount. Use a ref to avoid stale-closure issues
  // without adding onInteraction to the dep array (it's an inline arrow that
  // changes reference every render, which would retrigger the effect).
  const onInteractionRef = useRef(onInteraction);
  onInteractionRef.current = onInteraction;
  useEffect(() => {
    onInteractionRef.current("presented");
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleYes = () => {
    setPhase("detail");
    onInteraction("accepted");
  };

  const handleNo = () => {
    onInteraction("rejected");
  };

  if (phase === "prompt") {
    return (
      <div className="feedback-item">
        <div className="feedback-header">
          <span className="feedback-title">Feedback Available</span>
        </div>
        <p className="feedback-message">Do you want to see this feedback?</p>
        <div className="feedback-actions">
          <button className="feedback-action-btn" onClick={handleYes}>Yes</button>
          <button className="feedback-action-btn" onClick={handleNo}>No</button>
        </div>
      </div>
    );
  }

  return (
    <FeedbackDetailCard
      item={item}
      onInteraction={onInteraction}
    />
  );
}

interface FeedbackDetailCardProps {
  item: FeedbackItem;
  onInteraction: (type: InteractionType) => void;
}

function FeedbackDetailCard({ item, onInteraction }: FeedbackDetailCardProps) {
  const handleShowInCode = () => {
    onInteraction("highlighted");
  };

  const handleDone = () => {
    onInteraction("done");
  };

  const handleNotUseful = () => {
    onInteraction("dismissed");
  };

  return (
    <div className="feedback-item">
      <div className="feedback-header">
        <span className="feedback-title">{item.title}</span>
      </div>
      <p className="feedback-message">{item.message}</p>
      <div className="feedback-actions">
        {item.code_range && (
          <button className="feedback-action-btn" onClick={handleShowInCode}>
            Show in code
          </button>
        )}
        <button className="feedback-action-btn" onClick={handleDone}>Done</button>
        <button className="feedback-action-btn" onClick={handleNotUseful}>Not useful</button>
      </div>
    </div>
  );
}
