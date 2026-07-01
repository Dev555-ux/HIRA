"use client";

import { createContext, useContext } from "react";

export interface AuthUser {
  name: string;
  email: string;
  imageUrl: string | null;
}

export interface AuthContextValue {
  getToken: () => Promise<string | null>;
  user: AuthUser | null;
  isLoaded: boolean;
  mocked: boolean;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuthContext(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuthContext must be used within an AuthProvider");
  }
  return ctx;
}
