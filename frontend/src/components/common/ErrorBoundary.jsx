import { Component } from "react";
import Button from "./Button";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch() {
    // Keep the implementation detail out of the reviewer UI.
  }

  handleReload = () => {
    this.setState({ failed: false });
    window.location.reload();
  };

  render() {
    if (this.state.failed) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-paper px-6 text-ink">
          <div className="surface-elevated max-w-md px-6 py-8 text-center">
            <p className="meta mb-2">Workspace error</p>
            <h1 className="text-lg font-semibold tracking-tight">Something went wrong</h1>
            <p className="mt-2 text-sm leading-6 text-ink-muted">
              The workspace could not be displayed. Reload to try again. Your data was not modified.
            </p>
            <Button variant="primary" className="mt-5" onClick={this.handleReload}>
              Reload
            </Button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
