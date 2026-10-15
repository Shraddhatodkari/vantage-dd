import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import Login from "../pages/Login";
import ResetPassword from "../pages/ResetPassword";
import Account from "../pages/Account";
import { AuthProvider } from "../lib/auth";

const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers: { "content-type": "application/json" } });
const USER = { id: "u1", email: "a@x.io", full_name: "A", role: "analyst", is_active: true, is_demo_account: false, totp_enabled: false, failed_logins: 0, last_login_at: null };
const SESSION = { user: USER, permissions: ["deal:read"], access_expires_at: "2030-01-01T00:00:00Z", mfa_setup_required: false };

afterEach(() => { vi.unstubAllGlobals(); window.history.replaceState(null, "", "/"); });

describe("two-factor sign-in", () => {
  it("asks for the authenticator code after the password and sends only the code", async () => {
    const calls: { url: string; body?: string }[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, body: init?.body as string | undefined });
      if (url.endsWith("/meta")) return json({ app_name: "Vantage DD", env: "dev", demo_mode: false, demo_accounts: [], source_mode: "snapshot" });
      if (url.endsWith("/auth/session")) return json({ authenticated: false });
      if (url.endsWith("/auth/login")) return json({ mfa_required: true });
      if (url.endsWith("/auth/login/mfa")) return json({ detail: "Invalid or expired code" }, 401);
      return json({}, 404);
    }));
    render(<AuthProvider><MemoryRouter><Login /></MemoryRouter></AuthProvider>);
    await userEvent.type(screen.getByLabelText("Email"), "a@x.io");
    await userEvent.type(screen.getByLabelText("Password"), "Secret-Passw0rd!");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByTestId("mfa-step")).toBeInTheDocument();
    expect(screen.queryByLabelText("Password")).not.toBeInTheDocument();           // password cleared from the page
    await userEvent.type(screen.getByLabelText("Authentication code"), "12a3456");    // non-digits are dropped
    expect(screen.getByLabelText("Authentication code")).toHaveValue("123456");
    await userEvent.click(screen.getByRole("button", { name: /verify and sign in/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid or expired code");
    expect(screen.getByTestId("mfa-step")).toBeInTheDocument();                       // a wrong code keeps the code step
    const mfaCall = calls.find(c => c.url.endsWith("/auth/login/mfa"))!;
    expect(JSON.parse(mfaCall.body!)).toEqual({ code: "123456" });
  });
});

describe("password reset page", () => {
  it("reads the token from the fragment, removes it from the address bar and submits it", async () => {
    window.history.replaceState(null, "", "/reset-password#token=tok-abcdefghijklmnopqrstuvwxyz");
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<MemoryRouter><ResetPassword /></MemoryRouter>);
    await waitFor(() => expect(window.location.hash).toBe(""));
    expect(screen.getByLabelText("New password")).toHaveAttribute("type", "password");
    await userEvent.type(screen.getByLabelText("New password"), "Fresh-Passw0rd!x");
    await userEvent.type(screen.getByLabelText("Repeat new password"), "Fresh-Passw0rd!y");
    await userEvent.click(screen.getByRole("button", { name: "Set password" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("do not match");
    expect(fetchMock).not.toHaveBeenCalled();
    await userEvent.clear(screen.getByLabelText("Repeat new password"));
    await userEvent.type(screen.getByLabelText("Repeat new password"), "Fresh-Passw0rd!x");
    await userEvent.click(screen.getByRole("button", { name: "Set password" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Password set");
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({ token: "tok-abcdefghijklmnopqrstuvwxyz", new_password: "Fresh-Passw0rd!x" });
  });

  it("explains a link without a token", () => {
    window.history.replaceState(null, "", "/reset-password");
    vi.stubGlobal("fetch", vi.fn());
    render(<MemoryRouter><ResetPassword /></MemoryRouter>);
    expect(screen.getByRole("alert")).toHaveTextContent("no reset token");
  });
});

describe("account security", () => {
  it("shows the QR code and key during enrolment and turns 2FA on with a code", async () => {
    let enabled = false;
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.endsWith("/auth/session")) return json({ authenticated: true, ...SESSION, user: { ...USER, totp_enabled: enabled } });
      if (url.endsWith("/auth/mfa/setup")) return json({ secret: "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP", otpauth_uri: "otpauth://totp/x", qr_svg: "<svg xmlns='http://www.w3.org/2000/svg'></svg>" });
      if (url.endsWith("/auth/mfa/enable")) { enabled = true; return json({ ...SESSION, user: { ...USER, totp_enabled: true } }); }
      return json({}, 404);
    }));
    render(<AuthProvider><MemoryRouter><Account /></MemoryRouter></AuthProvider>);
    expect(await screen.findByTestId("mfa-status")).toHaveTextContent("Off");
    await userEvent.click(screen.getByRole("button", { name: /set up two-factor/i }));
    expect(await screen.findByAltText(/QR code/)).toHaveAttribute("src", expect.stringMatching(/^data:image\/svg\+xml;base64,/));
    expect(screen.getByTestId("mfa-secret")).toHaveTextContent("JBSW Y3DP");
    await userEvent.type(screen.getByLabelText(/6-digit code/), "123456");
    await userEvent.click(screen.getByRole("button", { name: /confirm and turn on/i }));
    expect(await screen.findByTestId("mfa-status")).toHaveTextContent("On");
    expect(screen.queryByTestId("mfa-secret")).not.toBeInTheDocument();             // key no longer displayed
  });
});
