import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FiCheckCircle, FiAlertTriangle, FiX } from "react-icons/fi";
import { evaluationService } from "../services/evaluation";

// Evaluations started in this browser that are still being graded. Kept in localStorage so the
// completion popup still shows after the user navigates away from the Evaluation page or reloads.
const STORAGE_KEY = "pendingEvaluations";
const POLL_INTERVAL_MS = 20000;
const MAX_PENDING_AGE_MS = 24 * 60 * 60 * 1000;

const readPending = () => {
  try {
    const list = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
};

const writePending = (list) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  } catch { }
};

const removePending = (evaluationId) => {
  writePending(readPending().filter(p => p.evaluationId !== evaluationId));
};

// Call when an evaluation has been started; the watcher shows a popup once it finishes.
export const trackPendingEvaluation = ({ evaluationId, name, courseId, courseTitle }) => {
  if (!evaluationId) return;
  const list = readPending().filter(p => p.evaluationId !== evaluationId);
  list.push({ evaluationId, name, courseId, courseTitle, startedAt: Date.now() });
  writePending(list);
};

export default function EvaluationCompletionWatcher() {
  const navigate = useNavigate();
  const [notices, setNotices] = useState([]); // queue of finished evaluations to announce
  const checkingRef = useRef(false);

  useEffect(() => {
    const check = async () => {
      if (checkingRef.current) return;
      const pending = readPending().filter(p => Date.now() - (p.startedAt || 0) < MAX_PENDING_AGE_MS);
      writePending(pending);
      if (pending.length === 0) return;

      checkingRef.current = true;
      try {
        for (const item of pending) {
          try {
            const status = await evaluationService.checkEvaluationStatus(item.evaluationId);
            if (status.status === "completed" || status.status === "failed") {
              removePending(item.evaluationId);
              setNotices(prev => [...prev, { ...item, failed: status.status === "failed", error: status.error || status.message }]);
            }
          } catch (err) {
            // Evaluation no longer exists: stop tracking it. Other errors: retry on the next poll.
            if ((err?.message || "").toLowerCase().includes("not found")) {
              removePending(item.evaluationId);
            }
          }
        }
      } finally {
        checkingRef.current = false;
      }
    };

    check();
    const timer = setInterval(check, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, []);

  if (notices.length === 0) return null;
  const notice = notices[0];

  const dismiss = () => setNotices(prev => prev.slice(1));
  const viewResults = () => {
    dismiss();
    try {
      if (notice.courseId) localStorage.setItem("currentCourseId", notice.courseId);
      if (notice.courseTitle) localStorage.setItem("currentCourseTitle", notice.courseTitle);
    } catch { }
    navigate(`/evaluation?evaluation_id=${encodeURIComponent(notice.evaluationId)}`);
  };

  const label = notice.name ? <strong style={{ color: "#111827" }}>"{notice.name}"</strong> : "your evaluation";

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(15, 23, 42, 0.45)", zIndex: 3000,
      display: "flex", alignItems: "center", justifyContent: "center", padding: 16
    }}>
      <div role="dialog" aria-modal="true" style={{
        position: "relative", width: "100%", maxWidth: 460, background: "#fff", borderRadius: 16,
        padding: "28px 28px 24px", boxShadow: "0 20px 50px rgba(15, 23, 42, 0.18)", textAlign: "center"
      }}>
        <button
          title="Close"
          onClick={dismiss}
          style={{ position: "absolute", top: 12, right: 12, background: "none", border: "none", cursor: "pointer", color: "#94a3b8", padding: 4 }}
        >
          <FiX size={18} />
        </button>
        <div style={{
          width: 56, height: 56, borderRadius: "50%", margin: "0 auto 14px auto",
          display: "flex", alignItems: "center", justifyContent: "center",
          background: notice.failed ? "#fef2f2" : "#ecfdf5", color: notice.failed ? "#dc2626" : "#059669"
        }}>
          {notice.failed ? <FiAlertTriangle size={26} /> : <FiCheckCircle size={26} />}
        </div>
        <h3 style={{ margin: "0 0 8px 0", fontSize: 20, fontWeight: 700, color: notice.failed ? "#b91c1c" : "#111827" }}>
          {notice.failed ? "Evaluation failed" : "Your evaluation is completed"}
        </h3>
        <p style={{ margin: "0 auto 22px auto", fontSize: 14, color: "#4b5563", lineHeight: 1.6 }}>
          {notice.failed
            ? <>Grading for {label} stopped due to an error.{notice.error ? <><br /><span style={{ fontSize: 13, color: "#7f1d1d" }}>{notice.error}</span></> : null}</>
            : <>Grading for {label}{notice.courseTitle ? <> in {notice.courseTitle}</> : null} is complete. You can check the results in the Evaluation card.</>}
        </p>
        <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
          <button
            onClick={dismiss}
            style={{ padding: "10px 22px", borderRadius: 10, border: "1px solid #d1d5db", background: "#fff", color: "#374151", fontWeight: 600, cursor: "pointer", fontSize: 14 }}
          >
            Close
          </button>
          <button
            onClick={viewResults}
            style={{ padding: "10px 22px", borderRadius: 10, border: "none", background: "#2563eb", color: "#fff", fontWeight: 600, cursor: "pointer", fontSize: 14 }}
          >
            {notice.failed ? "View details" : "View results"}
          </button>
        </div>
      </div>
    </div>
  );
}
