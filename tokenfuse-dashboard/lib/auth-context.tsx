"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import {
  getAuthToken,
  setAuthToken,
  clearAuthToken,
  getMe,
  login as apiLogin,
  signup as apiSignup,
} from "@/lib/api-client";

interface User {
  id: number;
  email: string;
  display_name: string | null;
  is_active: boolean;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getAuthToken();
    if (token) {
      getMe()
        .then(setUser)
        .catch(() => {
          clearAuthToken();
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  async function login(email: string, password: string) {
    const res = await apiLogin(email, password);
    setAuthToken(res.access_token);
    const me = await getMe();
    setUser(me);
  }

  async function signup(email: string, password: string, displayName?: string) {
    const res = await apiSignup(email, password, displayName);
    setAuthToken(res.access_token);
    const me = await getMe();
    setUser(me);
  }

  function logout() {
    clearAuthToken();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
