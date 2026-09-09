import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import UserMenu from "./UserMenu";

describe("UserMenu", () => {
  it("shows profile details and signs out through Auth0 logout", async () => {
    const onSignOut = vi.fn();
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <UserMenu
          user={{ name: "Ada Reviewer", email: "ada@example.test", picture: "" }}
          role="ADMIN"
          onSignOut={onSignOut}
        />
      </MemoryRouter>
    );
    expect(screen.getByText("Ada Reviewer")).toBeInTheDocument();
    expect(screen.getByText("ada@example.test")).toBeInTheDocument();
    expect(screen.getByText("ADMIN")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Ada Reviewer/i }));
    expect(screen.getByRole("menuitem", { name: "Profile" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Account" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("menuitem", { name: "Sign out" }));
    expect(onSignOut).toHaveBeenCalledTimes(1);
  });
});
