import { beforeEach, describe, expect, it, vi } from "vitest";
import { listenForPopupEvents, type EmbeddedSignupPopupEvent } from "./facebook-sdk";

vi.mock("./config", () => ({ facebookAppId: "test-app-id" }));

function post(origin: string, data: unknown) {
  window.dispatchEvent(
    new MessageEvent("message", {
      origin,
      data: typeof data === "string" ? data : JSON.stringify(data),
    }),
  );
}

function finish(overrides: Record<string, unknown> = {}) {
  return {
    type: "WA_EMBEDDED_SIGNUP",
    event: "FINISH",
    data: { waba_id: "WABA1", phone_number_id: "PN1", ...overrides },
  };
}

describe("listenForPopupEvents", () => {
  let events: EmbeddedSignupPopupEvent[];
  let stop: () => void;

  beforeEach(() => {
    events = [];
    stop = listenForPopupEvents((event) => events.push(event));
  });

  it("reports the WABA and phone number Meta's popup selected", () => {
    post("https://www.facebook.com", finish());
    stop();

    expect(events).toEqual([{ kind: "finished", wabaId: "WABA1", phoneNumberId: "PN1" }]);
  });

  it("distinguishes cancelling from erroring", () => {
    post("https://www.facebook.com", {
      type: "WA_EMBEDDED_SIGNUP",
      event: "CANCEL",
      data: { current_step: "PHONE_NUMBER" },
    });
    post("https://www.facebook.com", {
      type: "WA_EMBEDDED_SIGNUP",
      event: "ERROR",
      data: { error_message: "nope" },
    });
    stop();

    expect(events.map((e) => e.kind)).toEqual(["cancelled", "error"]);
  });

  it("ignores lookalike origins", () => {
    // The reason this module uses an exact allowlist rather than the
    // commonly-copied `origin.endsWith("facebook.com")`: this origin
    // passes that check.
    post("https://evilfacebook.com", finish());
    post("https://facebook.com.attacker.test", finish());
    post("http://www.facebook.com", finish());
    stop();

    expect(events).toEqual([]);
  });

  it("ignores unrelated and malformed messages from a trusted origin", () => {
    post("https://www.facebook.com", "not json at all");
    post("https://www.facebook.com", { type: "SOMETHING_ELSE" });
    post("https://www.facebook.com", null);
    stop();

    expect(events).toEqual([]);
  });

  it("tolerates a FINISH that reports no ids", () => {
    post("https://www.facebook.com", {
      type: "WA_EMBEDDED_SIGNUP",
      event: "FINISH",
      data: {},
    });
    stop();

    expect(events).toEqual([{ kind: "finished", wabaId: undefined, phoneNumberId: undefined }]);
  });

  it("stops listening once unsubscribed", () => {
    stop();
    post("https://www.facebook.com", finish());

    expect(events).toEqual([]);
  });
});
