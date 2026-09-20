"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  launchEmbeddedSignup,
  listenForPopupEvents,
  loadFacebookSdk,
  type EmbeddedSignupPopupEvent,
} from "@/lib/facebook-sdk";
import { api } from "@/lib/api";
import { useAuthContext } from "@/lib/auth-context";
import type { EmbeddedSignupErrorCode } from "@/lib/types";

/** Where the flow currently is. The UI renders one screen per phase, so
 * these are deliberately the *owner's* stages, not the API's:
 * `connecting` covers the whole backend sequence (token exchange, number
 * registration, webhook subscription), which DEC-052 §3.6 specifies as one
 * uninterrupted "setting up" moment rather than three exposed steps. */
export type EmbeddedSignupPhase =
  | "idle"
  | "opening"
  | "awaiting_popup"
  | "connecting"
  | "success"
  | "error";

/** Backend failures, plus the two that can only happen in the browser and
 * therefore have no server-side equivalent. */
export type EmbeddedSignupFailure =
  | EmbeddedSignupErrorCode
  | "sdk_unavailable"
  | "popup_closed"
  | "network_error";

interface State {
  phase: EmbeddedSignupPhase;
  failure: EmbeddedSignupFailure | null;
  displayPhoneNumber: string | null;
}

const INITIAL: State = { phase: "idle", failure: null, displayPhoneNumber: null };

export function useEmbeddedSignup() {
  const { getToken } = useAuthContext();
  const queryClient = useQueryClient();
  const [state, setState] = useState<State>(INITIAL);

  const unsubscribe = useRef<(() => void) | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      unsubscribe.current?.();
      unsubscribe.current = null;
    };
  }, []);

  const set = useCallback((next: Partial<State>) => {
    // The popup outlives a navigation away from this page; without this
    // guard a late resolution would set state on an unmounted component.
    if (mounted.current) setState((current) => ({ ...current, ...next }));
  }, []);

  const reset = useCallback(() => set(INITIAL), [set]);

  const start = useCallback(async () => {
    // Local to this attempt, not a ref: the popup's report is only
    // meaningful within the single run that opened it, so a cancelled run
    // can't leak hints into the next one.
    let reported: EmbeddedSignupPopupEvent | null = null;
    set({ phase: "opening", failure: null, displayPhoneNumber: null });

    let sdk;
    try {
      sdk = await loadFacebookSdk();
    } catch {
      set({ phase: "error", failure: "sdk_unavailable" });
      return;
    }

    let session;
    try {
      session = await api.startEmbeddedSignup(getToken);
    } catch {
      set({ phase: "error", failure: "network_error" });
      return;
    }

    unsubscribe.current?.();
    unsubscribe.current = listenForPopupEvents((event) => {
      reported = event;
    });

    set({ phase: "awaiting_popup" });
    const code = await launchEmbeddedSignup(sdk, session.config_id);

    unsubscribe.current?.();
    unsubscribe.current = null;

    if (!code) {
      // No code means the owner never completed Meta's screens. The
      // popup's own last message distinguishes "closed the window" from
      // "declined a permission" — different problems, different advice.
      const event = reported as EmbeddedSignupPopupEvent | null;
      set({
        phase: "error",
        failure: event?.kind === "error" ? "permission_denied" : "popup_closed",
      });
      return;
    }

    set({ phase: "connecting" });
    // Asserted because TypeScript's control-flow analysis can't see the
    // listener callback above assigning to this local.
    const finished = reported as EmbeddedSignupPopupEvent | null;
    const hints = finished?.kind === "finished" ? finished : undefined;

    let result;
    try {
      result = await api.completeEmbeddedSignup(getToken, {
        code,
        state: session.state,
        waba_id: hints?.wabaId,
        phone_number_id: hints?.phoneNumberId,
      });
    } catch {
      set({ phase: "error", failure: "network_error" });
      return;
    }

    if (!result.success) {
      set({ phase: "error", failure: result.error_code ?? "token_exchange_failed" });
      return;
    }

    // The connection status badge, the onboarding checklist and the
    // Settings card all read this query.
    queryClient.invalidateQueries({ queryKey: ["whatsapp-status"] });
    set({ phase: "success", displayPhoneNumber: result.display_phone_number, failure: null });
  }, [getToken, queryClient, set]);

  return { ...state, start, reset };
}
