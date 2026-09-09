"use client";

import { ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";

type FeedbackReason = "incomplete" | "outdated" | "hard_to_follow" | "other";

export function ArticleFeedback({
  articleId,
  path,
  connected,
}: {
  articleId: string;
  path: string;
  connected: boolean;
}) {
  const [choice, setChoice] = useState<"yes" | "no" | null>(null);
  const [reason, setReason] = useState<FeedbackReason>("incomplete");
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | "error">("idle");

  async function submit(helpful: boolean, selectedReason?: FeedbackReason) {
    setChoice(helpful ? "yes" : "no");
    if (!connected) {
      setStatus("sent");
      return;
    }
    setStatus("sending");
    try {
      const response = await fetch("/api/backend/learning-events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event_type: "article_feedback",
          article_id: articleId,
          path,
          helpful,
          reason: helpful ? "clear" : selectedReason,
        }),
      });
      if (!response.ok) throw new Error("feedback request failed");
      setStatus("sent");
    } catch {
      setStatus("error");
    }
  }

  return (
    <section className="article-feedback" aria-labelledby={`feedback-${articleId}`}>
      <div>
        <h2 id={`feedback-${articleId}`}>Was this article helpful?</h2>
        <p>No free-text response is collected.</p>
      </div>
      {status === "sent" ? (
        <p className="article-feedback-status" role="status">
          {connected
            ? "Thanks—your response will help improve Learn PolicyOS."
            : "Thanks. Demo mode does not save feedback."}
        </p>
      ) : (
        <div className="article-feedback-form">
          <div className="article-feedback-actions" aria-label="Rate this article">
            <button
              type="button"
              className="button secondary"
              onClick={() => submit(true)}
              disabled={status === "sending"}
            >
              <ThumbsUp size={14} /> Yes
            </button>
            <button
              type="button"
              className="button secondary"
              onClick={() => {
                setChoice("no");
                setStatus("idle");
              }}
              disabled={status === "sending"}
            >
              <ThumbsDown size={14} /> Not yet
            </button>
          </div>
          {choice === "no" && (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                submit(false, reason);
              }}
            >
              <label htmlFor={`feedback-reason-${articleId}`}>What should we improve?</label>
              <select
                id={`feedback-reason-${articleId}`}
                className="select"
                value={reason}
                onChange={(event) => setReason(event.target.value as FeedbackReason)}
              >
                <option value="incomplete">Missing information</option>
                <option value="outdated">Does not match the product</option>
                <option value="hard_to_follow">Hard to follow</option>
                <option value="other">Something else</option>
              </select>
              <button type="submit" className="button primary" disabled={status === "sending"}>
                {status === "sending" ? "Sending…" : "Send feedback"}
              </button>
            </form>
          )}
          {status === "error" && (
            <p className="article-feedback-error" role="alert">
              Feedback could not be saved. Please try again.
            </p>
          )}
        </div>
      )}
    </section>
  );
}
