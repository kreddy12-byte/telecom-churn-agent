import { useState } from "react";
import { Link } from "react-router-dom";
import Button from "../common/Button";
import Modal from "../common/Modal";
import StatusBadge from "../common/StatusBadge";
import { formatDate, formatPercent, strategyLabel } from "../../utils/format";

const STRATEGIES = [
  "CONTRACT_CONVERSION",
  "PRICING_VALUE",
  "SUPPORT_INTERVENTION",
  "SERVICE_BUNDLE_OPTIMIZATION",
  "EARLY_LIFECYCLE_ONBOARDING",
  "GENERAL_RETENTION_REVIEW",
];

const WORKFLOW = ["PENDING", "APPROVED", "MODIFIED", "REJECTED"];

const CONFIRMATION = {
  APPROVED: "Retention action approved",
  MODIFIED: "Retention action modified",
  REJECTED: "Retention action rejected",
};

export default function DecisionPanel({
  customerId,
  recommendation,
  probability,
  currentAction,
  busy,
  onApprove,
  onModify,
  onReject,
  onNewReview,
}) {
  const [dialog, setDialog] = useState(null);
  const [note, setNote] = useState("");
  const [strategyId, setStrategyId] = useState(
    recommendation?.selected_strategy?.strategy_id || STRATEGIES[0]
  );
  const [revised, setRevised] = useState(recommendation?.recommendation || "");

  const currentStatus = currentAction?.status || null;
  const pending = currentAction?.status === "PENDING" || currentAction?.status === "MODIFIED";
  const decided =
    currentAction?.status === "APPROVED" || currentAction?.status === "REJECTED";

  function close() {
    setDialog(null);
    setNote("");
  }

  return (
    <div className="space-y-4">
      <p className="text-sm font-medium text-ink">The system recommends. A human decides.</p>

      <ol className="flex flex-wrap items-center gap-1.5" aria-label="Review workflow">
        {WORKFLOW.map((step, index) => {
          const active = Boolean(currentAction) && currentStatus === step;
          return (
            <li key={step} className="flex items-center gap-1.5">
              {index > 0 ? (
                <span className="text-[11px] text-ink-faint" aria-hidden="true">
                  →
                </span>
              ) : null}
              <span
                className={`rounded-panel border px-2 py-1 text-[11px] font-semibold tracking-wide ${
                  active ? "border-accent bg-accent-soft text-accent" : "border-line text-ink-faint"
                }`}
              >
                {step}
              </span>
            </li>
          );
        })}
      </ol>

      {decided && currentAction ? (
        <div
          role="status"
          className="rounded-panel border border-success/35 bg-success-soft px-4 py-3"
        >
          <p className="text-sm font-semibold text-success">
            {CONFIRMATION[currentAction.status] || "Retention action recorded"}
          </p>
          <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-xs text-ink-muted">Action</dt>
              <dd className="mt-0.5 text-ink">
                {strategyLabel(currentAction.strategy_id)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-ink-muted">Customer</dt>
              <dd className="mt-0.5 text-ink">{currentAction.customer_id}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-muted">Reviewer</dt>
              <dd className="mt-0.5 text-ink">
                {currentAction.reviewed_by_name || currentAction.reviewed_by_email || "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-ink-muted">Timestamp</dt>
              <dd className="mt-0.5 text-ink">{formatDate(currentAction.updated_at)}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-muted">Status</dt>
              <dd className="mt-0.5">
                <StatusBadge status={currentAction.status} />
              </dd>
            </div>
          </dl>
          <p className="mt-3">
            <Link to="/actions" className="text-sm font-medium text-accent hover:underline">
              View retention actions
            </Link>
          </p>
        </div>
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-faint">
              Current record
            </p>
            <div className="mt-1">
              {currentAction ? (
                <StatusBadge status={currentAction.status} />
              ) : (
                <span className="text-sm text-ink-faint">No action yet</span>
              )}
            </div>
          </div>
          {currentAction?.reviewer_note ? (
            <p className="max-w-md text-sm text-ink-muted">{currentAction.reviewer_note}</p>
          ) : null}
        </div>
      )}

      {decided ? (
        <div className="flex flex-wrap items-center gap-3">
          <p className="text-sm text-ink-muted">
            This decision is final. Raise a new review if the case should be reconsidered.
          </p>
          <Button onClick={onNewReview} disabled={busy}>
            New review
          </Button>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          <Button variant="primary" disabled={busy} onClick={() => setDialog("approve")}>
            Approve
          </Button>
          <Button disabled={busy} onClick={() => setDialog("modify")}>
            Modify
          </Button>
          <Button variant="danger" disabled={busy} onClick={() => setDialog("reject")}>
            Reject
          </Button>
        </div>
      )}

      {dialog === "approve" ? (
        <Modal title="Confirm approval" onClose={close}>
          <p className="text-sm leading-6 text-ink">
            This records that a human approved the recommendation. It does not
            contact the customer or change their account.
          </p>
          <ul className="mt-3 space-y-1 text-sm text-ink-muted">
            <li>Customer: {customerId}</li>
            <li>
              Strategy:{" "}
              {strategyLabel(recommendation?.selected_strategy?.strategy_id)}
            </li>
            <li>Model estimate: {formatPercent(probability)}</li>
          </ul>
          <div className="mt-5 flex justify-end gap-2">
            <Button onClick={close}>Cancel</Button>
            <Button
              variant="primary"
              disabled={busy}
              onClick={() => onApprove().then(close)}
            >
              Confirm approval
            </Button>
          </div>
        </Modal>
      ) : null}

      {dialog === "modify" ? (
        <Modal title="Modify recommendation" onClose={close}>
          <div className="space-y-3">
            <label className="block text-sm" htmlFor="modify-strategy">
              <span className="text-ink-muted">Strategy</span>
              <select
                id="modify-strategy"
                className="field-input mt-1"
                value={strategyId}
                onChange={(event) => setStrategyId(event.target.value)}
              >
                {STRATEGIES.map((id) => (
                  <option key={id} value={id}>
                    {strategyLabel(id)}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm" htmlFor="modify-wording">
              <span className="text-ink-muted">Revised wording</span>
              <textarea
                id="modify-wording"
                className="field-input mt-1"
                rows={3}
                value={revised}
                onChange={(event) => setRevised(event.target.value)}
              />
            </label>
            <label className="block text-sm" htmlFor="modify-note">
              <span className="text-ink-muted">Reviewer note (required)</span>
              <textarea
                id="modify-note"
                className="field-input mt-1"
                rows={3}
                value={note}
                onChange={(event) => setNote(event.target.value)}
              />
            </label>
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <Button onClick={close}>Cancel</Button>
            <Button
              variant="primary"
              disabled={busy || !note.trim()}
              onClick={() =>
                onModify({
                  strategyId,
                  recommendation: revised,
                  reviewerNote: note.trim(),
                }).then(close)
              }
            >
              Save modification
            </Button>
          </div>
        </Modal>
      ) : null}

      {dialog === "reject" ? (
        <Modal title="Reject recommendation" onClose={close}>
          <label className="block text-sm" htmlFor="reject-note">
            <span className="text-ink-muted">Reason (required)</span>
            <textarea
              id="reject-note"
              className="field-input mt-1"
              rows={4}
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
          </label>
          <div className="mt-5 flex justify-end gap-2">
            <Button onClick={close}>Cancel</Button>
            <Button
              variant="danger"
              disabled={busy || !note.trim()}
              onClick={() => onReject(note.trim()).then(close)}
            >
              Confirm rejection
            </Button>
          </div>
        </Modal>
      ) : null}

      {!pending && !decided ? (
        <p className="text-xs text-ink-muted">
          Approving, modifying, or rejecting creates a pending record first, then
          stores the human decision. Nothing is sent to the customer.
        </p>
      ) : null}
    </div>
  );
}
