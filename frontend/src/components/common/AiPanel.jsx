import Badge from "./Badge";

/**
 * Subtle chrome for AI-generated recommendation content.
 * Distinct from model output, SHAP explanation, and human decision panels.
 */
export default function AiPanel({ title, children, className = "", badge = "AI recommendation" }) {
  return (
    <section className={`ai-panel ${className}`}>
      <div className="mb-3 flex flex-wrap items-center gap-2 pl-2">
        <Badge tone="ai">{badge}</Badge>
        {title ? <h3 className="card-title">{title}</h3> : null}
      </div>
      <div className="pl-2">{children}</div>
    </section>
  );
}
