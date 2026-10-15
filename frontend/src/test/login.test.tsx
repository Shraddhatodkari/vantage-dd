import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Login from "../pages/Login";
import { AuthProvider } from "../lib/auth";

function mockFetch(meta: object) {
  return vi.fn(async (url: string) => {
    if (url.endsWith("/meta")) return new Response(JSON.stringify(meta), { status: 200, headers: { "content-type": "application/json" } });
    if (url.endsWith("/auth/session")) return new Response(JSON.stringify({ authenticated: false }), { status: 200, headers: { "content-type": "application/json" } });
    if (url.endsWith("/auth/me")) return new Response(JSON.stringify({ detail: "Not authenticated" }), { status: 401, headers: { "content-type": "application/json" } });
    if (url.endsWith("/auth/refresh")) return new Response("{}", { status: 401 });
    if (url.endsWith("/auth/login")) return new Response(JSON.stringify({ detail: "Invalid email or password" }), { status: 401, headers: { "content-type": "application/json" } });
    return new Response("{}", { status: 404 });
  });
}

const renderLogin = () => render(<AuthProvider><MemoryRouter><Login /></MemoryRouter></AuthProvider>);

describe("Login page", () => {
  beforeEach(() => { vi.stubGlobal("fetch", mockFetch({ app_name: "Vantage DD", env: "dev", demo_mode: true, source_mode: "snapshot",
    demo_accounts: [{ email: "analyst@vantage.dev", role: "analyst" }, { email: "partner@vantage.dev", role: "partner" }] })); });
  afterEach(() => vi.unstubAllGlobals());

  it("never shows a password and masks the input by default", async () => {
    renderLogin();
    await screen.findByTestId("demo-accounts");
    expect(document.body.textContent).not.toMatch(new RegExp(["Vantage", "2026"].join("@") + "|Password:\\s*\\S+@"));
    expect(screen.getByLabelText("Password")).toHaveAttribute("type", "password");
  });

  it("eye button reveals and hides only what the user typed", async () => {
    renderLogin();
    const pw = screen.getByLabelText("Password");
    await userEvent.type(pw, "my-secret");
    await userEvent.click(screen.getByRole("button", { name: "Show password" }));
    expect(pw).toHaveAttribute("type", "text");
    await userEvent.click(screen.getByRole("button", { name: "Hide password" }));
    expect(pw).toHaveAttribute("type", "password");
  });

  it("demo chips fill the email only", async () => {
    renderLogin();
    await userEvent.click(await screen.findByRole("button", { name: "partner" }));
    expect(screen.getByLabelText("Email")).toHaveValue("partner@vantage.dev");
    expect(screen.getByLabelText("Password")).toHaveValue("");
  });

  it("shows no demo accounts when demo mode is off", async () => {
    vi.stubGlobal("fetch", mockFetch({ app_name: "Vantage DD", env: "prod", demo_mode: false, source_mode: "snapshot", demo_accounts: [] }));
    renderLogin();
    await waitFor(() => expect(screen.queryByTestId("demo-accounts")).not.toBeInTheDocument());
  });

  it("shows the server's generic error on failed login", async () => {
    renderLogin();
    await userEvent.type(screen.getByLabelText("Email"), "analyst@vantage.dev");
    await userEvent.type(screen.getByLabelText("Password"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password");
  });
});
