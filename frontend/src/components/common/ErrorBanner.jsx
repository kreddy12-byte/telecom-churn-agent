import Button from "./Button";
import { Alert } from "./Alert";

export default function ErrorBanner({ message, onRetry }) {
  return (
    <Alert tone="error" onRetry={onRetry}>
      {message || "Unable to load this view."}
    </Alert>
  );
}
