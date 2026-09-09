export default function RetentionPriorityPanel() {
  const steps = [
    {
      n: "1",
      title: "Identify",
      body: "High-risk customers from the scored population.",
    },
    {
      n: "2",
      title: "Understand",
      body: "SHAP explanation and the customer's service context.",
    },
    {
      n: "3",
      title: "Act",
      body: "Recommendation, what-if scenarios, and human approval.",
    },
  ];

  return (
    <div>
      <p className="text-sm leading-6 text-ink-muted">
        Use predicted risk to prioritize customers for investigation. View
        intelligence for a high-risk customer to explain the prediction,
        recommend a retention action, simulate interventions, and record a
        human decision.
      </p>
      <ol className="mt-4 grid gap-3 sm:grid-cols-3">
        {steps.map((step) => (
          <li key={step.n} className="border border-line bg-slate-50 px-3 py-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-faint">
              Step {step.n}
            </p>
            <p className="mt-1 text-sm font-semibold text-ink">{step.title}</p>
            <p className="mt-1 text-sm leading-5 text-ink-muted">{step.body}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}
