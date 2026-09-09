import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ErrorBoundary from "./ErrorBoundary";

function Broken() {
  throw new Error("internal render failure");
}

describe("ErrorBoundary", () => {
  it("shows a safe recovery message instead of a blank page", () => {
    const spy = console.error;
    console.error = () => {};
    render(
      <ErrorBoundary>
        <Broken />
      </ErrorBoundary>
    );
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reload" })).toBeInTheDocument();
    expect(screen.queryByText(/internal render failure/i)).not.toBeInTheDocument();
    console.error = spy;
  });
});
