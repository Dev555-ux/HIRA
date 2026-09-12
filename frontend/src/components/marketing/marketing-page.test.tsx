import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { MarketingPage } from "./marketing-page";

describe("MarketingPage", () => {
  it("renders exactly one h1 leading with the customer's problem", () => {
    render(<MarketingPage />);

    const headings = screen.getAllByRole("heading", { level: 1 });
    expect(headings).toHaveLength(1);
    expect(headings[0]).toHaveTextContent(/never miss another customer message/i);
  });

  it("shows a Founder Beta badge", () => {
    render(<MarketingPage />);

    expect(screen.getByText(/founder beta/i)).toBeInTheDocument();
  });

  it("proves the product with the Mission Control signature demo below the hero", () => {
    render(<MarketingPage />);

    // The demo opens idle by design (see signature-demo.test.tsx for the
    // full script) — here we only confirm the accessible entry point for
    // the demo exists on the page, without needing fake timers.
    expect(
      screen.getByRole("group", { name: /four.*systems/i }),
    ).toBeInTheDocument();
  });

  it("answers who HIRA is built for right below the hero", () => {
    render(<MarketingPage />);

    expect(screen.getByText("Built for")).toBeInTheDocument();
    expect(screen.getByText("Dental Clinics")).toBeInTheDocument();
    expect(screen.getByText("Professional Services")).toBeInTheDocument();
  });

  it("shows a lightweight trust checklist of things HIRA does today", () => {
    render(<MarketingPage />);

    expect(screen.getByText("Replies automatically")).toBeInTheDocument();
    expect(screen.getByText("Escalates to humans")).toBeInTheDocument();
  });

  it("walks the message-to-finished-job journey in order", () => {
    render(<MarketingPage />);

    const steps = screen.getAllByRole("listitem").filter((li) => /^0[1-5]$/.test(li.textContent?.slice(0, 2) ?? ""));
    expect(steps.map((li) => li.textContent?.slice(0, 2))).toEqual(["01", "02", "03", "04", "05"]);
  });

  it("links every primary CTA to sign-up", () => {
    render(<MarketingPage />);

    const ctaLinks = screen.getAllByRole("link", { name: /get started/i });
    expect(ctaLinks.length).toBeGreaterThan(0);
    for (const link of ctaLinks) {
      expect(link).toHaveAttribute("href", "/sign-up");
    }
  });

  it("links Sign in to the sign-in route", () => {
    render(<MarketingPage />);

    const signInLinks = screen.getAllByRole("link", { name: /sign in/i });
    expect(signInLinks.length).toBeGreaterThan(0);
    for (const link of signInLinks) {
      expect(link).toHaveAttribute("href", "/sign-in");
    }
  });

  it("has a skip-to-content link targeting the main landmark", () => {
    render(<MarketingPage />);

    const skipLink = screen.getByRole("link", { name: /skip to content/i });
    expect(skipLink).toHaveAttribute("href", "#main-content");
    expect(screen.getByRole("main")).toHaveAttribute("id", "main-content");
  });

  it("renders every requested section as a labeled heading", () => {
    render(<MarketingPage />);

    const h2s = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(h2s.some((t) => /finished job/i.test(t ?? ""))).toBe(true); // Journey
    expect(h2s.some((t) => /whatsapp/i.test(t ?? ""))).toBe(true); // Problem
    expect(h2s.some((t) => /bundle of bots/i.test(t ?? ""))).toBe(true); // Solution
    expect(h2s.some((t) => /ai employees/i.test(t ?? ""))).toBe(true); // AI Employees
    expect(h2s.some((t) => /front desk/i.test(t ?? ""))).toBe(true); // Features
    expect(h2s.some((t) => /four steps/i.test(t ?? ""))).toBe(true); // How it works
    expect(h2s.some((t) => /frequently asked/i.test(t ?? ""))).toBe(true); // FAQ
    expect(h2s.some((t) => /never miss another message again/i.test(t ?? ""))).toBe(true); // Final CTA
  });

  it("never claims HIRA is an 'AI receptionist' anywhere on the page", () => {
    const { container } = render(<MarketingPage />);

    expect(container.textContent).not.toMatch(/AI receptionist/i);
  });

  it("directly addresses the chatbot question in the FAQ", () => {
    render(<MarketingPage />);

    expect(screen.getByText("Is HIRA a chatbot?")).toBeInTheDocument();
  });

  it("marks only the Receptionist as available now, not future roles", () => {
    render(<MarketingPage />);

    expect(screen.getByText("Available now")).toBeInTheDocument();
    expect(screen.getByText("Sales follow-up")).toBeInTheDocument();
    expect(screen.getByText("Support")).toBeInTheDocument();
  });

  it("does not claim a public price", () => {
    render(<MarketingPage />);

    expect(screen.getByText(/pricing isn't public yet/i)).toBeInTheDocument();
  });

  it("expands a FAQ answer on click", async () => {
    const user = userEvent.setup();
    render(<MarketingPage />);

    const question = screen.getByText("Can it actually book appointments?");
    const details = question.closest("details");
    expect(details).not.toBeNull();
    expect(details).not.toHaveAttribute("open");

    await user.click(question);

    expect(details).toHaveAttribute("open");
  });

  it("renders the footer with a copyright line", () => {
    render(<MarketingPage />);

    expect(screen.getByText(new RegExp(`© ${new Date().getFullYear()} HIRA`))).toBeInTheDocument();
  });
});
