// Meta's JavaScript SDK: loading it, and the two things Embedded Signup
// needs from it (Sprint 83).
//
// Two separate channels carry the result of Meta's popup, and both are
// required — this is the part of Embedded Signup that surprises people:
//
//   1. `FB.login`'s own callback returns the **authorization code**. That
//      code is the only thing with real authority, and it's worthless
//      without the app secret, which lives on the backend.
//   2. A `postMessage` from Meta's popup reports **which WABA and phone
//      number** the owner picked, plus whether they cancelled or errored
//      partway through. It carries no credential.
//
// The postMessage half arrives from a window we don't control, so it is
// treated as untrusted throughout: the origin is checked against an exact
// allowlist, and the ids it reports are sent to the backend as hints that
// the backend re-verifies against the token's own granular scopes.

import { facebookAppId } from "./config";

// Meta's SDK version for the popup. Kept beside the loader (rather than in
// env config) because it pins a *client-side script contract*, not a
// deployment setting — changing it means re-testing the popup itself.
const SDK_VERSION = "v21.0";
const SDK_SRC = `https://connect.facebook.net/en_US/sdk.js`;
const SDK_ELEMENT_ID = "facebook-jssdk";

// Exact origins, never a suffix match. `origin.endsWith("facebook.com")` is
// the common version of this check and it is wrong: "evilfacebook.com" ends
// with "facebook.com" too.
const TRUSTED_ORIGINS = ["https://www.facebook.com", "https://web.facebook.com"];

export type EmbeddedSignupPopupEvent =
  | { kind: "finished"; wabaId?: string; phoneNumberId?: string }
  | { kind: "cancelled"; step?: string }
  | { kind: "error"; message?: string };

interface FacebookLoginResponse {
  authResponse?: { code?: string } | null;
  status?: string;
}

interface FacebookSdk {
  init(options: { appId: string; cookie?: boolean; xfbml?: boolean; version: string }): void;
  login(
    callback: (response: FacebookLoginResponse) => void,
    options: Record<string, unknown>,
  ): void;
}

declare global {
  interface Window {
    FB?: FacebookSdk;
    fbAsyncInit?: () => void;
  }
}

let loader: Promise<FacebookSdk> | null = null;

/** Loads and initializes Meta's SDK once per page, returning the same
 * promise to every later caller. Rejects if the script can't load at all —
 * an ad blocker, an offline browser, a CSP — which the UI surfaces as
 * "couldn't reach Facebook" rather than a button that silently does
 * nothing. */
export function loadFacebookSdk(): Promise<FacebookSdk> {
  if (loader) return loader;

  loader = new Promise<FacebookSdk>((resolve, reject) => {
    if (typeof window === "undefined") {
      reject(new Error("The Facebook SDK can only load in a browser"));
      return;
    }
    if (!facebookAppId) {
      reject(new Error("NEXT_PUBLIC_FACEBOOK_APP_ID is not configured"));
      return;
    }
    if (window.FB) {
      resolve(window.FB);
      return;
    }

    const initialize = () => {
      if (!window.FB) {
        reject(new Error("The Facebook SDK loaded but did not initialize"));
        return;
      }
      window.FB.init({
        appId: facebookAppId,
        cookie: true,
        xfbml: false,
        version: SDK_VERSION,
      });
      resolve(window.FB);
    };

    const existing = document.getElementById(SDK_ELEMENT_ID);
    if (existing) {
      // Another mount started the load; wait for the same init hook.
      window.fbAsyncInit = initialize;
      return;
    }

    window.fbAsyncInit = initialize;
    const script = document.createElement("script");
    script.id = SDK_ELEMENT_ID;
    script.src = SDK_SRC;
    script.async = true;
    script.defer = true;
    script.crossOrigin = "anonymous";
    script.onerror = () => {
      loader = null; // let a retry try again rather than caching the failure
      reject(new Error("Could not load the Facebook SDK"));
    };
    document.body.appendChild(script);
  });

  return loader;
}

/** Subscribes to Meta's popup messages. Returns the unsubscribe function.
 *
 * Everything here is defensive on purpose: this listener sees every
 * postMessage the page receives, most of them from unrelated scripts. */
export function listenForPopupEvents(
  onEvent: (event: EmbeddedSignupPopupEvent) => void,
): () => void {
  const handler = (event: MessageEvent) => {
    if (!TRUSTED_ORIGINS.includes(event.origin)) return;

    let payload: unknown;
    try {
      payload = typeof event.data === "string" ? JSON.parse(event.data) : event.data;
    } catch {
      return; // not ours; plenty of scripts postMessage non-JSON strings
    }
    if (!payload || typeof payload !== "object") return;

    const message = payload as {
      type?: string;
      event?: string;
      data?: { phone_number_id?: string; waba_id?: string; current_step?: string; error_message?: string };
    };
    if (message.type !== "WA_EMBEDDED_SIGNUP") return;

    const data = message.data ?? {};
    if (message.event === "FINISH") {
      onEvent({ kind: "finished", wabaId: data.waba_id, phoneNumberId: data.phone_number_id });
    } else if (message.event === "CANCEL") {
      onEvent({ kind: "cancelled", step: data.current_step });
    } else {
      onEvent({ kind: "error", message: data.error_message });
    }
  };

  window.addEventListener("message", handler);
  return () => window.removeEventListener("message", handler);
}

/** Opens Embedded Signup and resolves with the authorization code, or null
 * if the owner closed the popup or declined. */
export function launchEmbeddedSignup(sdk: FacebookSdk, configId: string): Promise<string | null> {
  return new Promise((resolve) => {
    sdk.login(
      (response) => resolve(response?.authResponse?.code ?? null),
      {
        config_id: configId,
        // Embedded Signup returns a code, not a token: the browser must
        // never hold anything that can call the Graph API on its own.
        response_type: "code",
        override_default_response_type: true,
        extras: { setup: {}, featureType: "", sessionInfoVersion: "3" },
      },
    );
  });
}
