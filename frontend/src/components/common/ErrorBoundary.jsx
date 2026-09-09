import { Component } from "react";

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
          <div className="max-w-md border border-line bg-white px-6 py-8 text-center">
            <h1 className="text-lg font-semibold">Something went wrong</h1>
            <p className="mt-2 text-sm text-ink-muted">
              The workspace could not be displayed. Reload to try again.
            </p>
            <button
              type="button"
              onClick={this.handleReload}
              className="mt-5 bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"
            >
              Reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
