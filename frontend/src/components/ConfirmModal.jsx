import { useEffect } from "react";

export default function ConfirmModal({ title, message, confirmLabel = "Confirm", onConfirm, onCancel }) {
  useEffect(() => {
    function onKey(e) { if (e.key === "Escape") onCancel(); }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onCancel]);

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>{title}</h3>
        <p>{message}</p>
        <div className="modal-actions">
          <button className="btn-cancel" onClick={onCancel}>Cancel</button>
          <button className="btn-stop" onClick={onConfirm}>{confirmLabel}</button>
        </div>
      </div>
    </div>
  );
}
