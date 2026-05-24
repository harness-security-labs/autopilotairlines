import { create } from "zustand";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface AuthState {
  token: string | null;
  user: { email: string; role: string; name: string } | null;
  login: (email: string, password: string) => Promise<boolean>;
  register: (email: string, password: string, name?: string, date_of_birth?: string) => Promise<boolean>;
  logout: () => void;
  loadToken: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  user: null,
  login: async (email: string, password: string) => {
    try {
      const res = await fetch(`${API_URL}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) return false;
      const data = await res.json();
      const token = data.access_token;
      localStorage.setItem("token", token);
      const payload = JSON.parse(atob(token.split(".")[1]));
      set({ token, user: { email: payload.email, role: payload.role, name: payload.email.split("@")[0] } });
      return true;
    } catch {
      return false;
    }
  },
  register: async (email: string, password: string, name?: string, date_of_birth?: string) => {
    try {
      const res = await fetch(`${API_URL}/api/v1/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, name: name || undefined, date_of_birth }),
      });
      if (!res.ok) return false;
      const data = await res.json();
      const token = data.access_token;
      localStorage.setItem("token", token);
      const payload = JSON.parse(atob(token.split(".")[1]));
      set({ token, user: { email: payload.email, role: payload.role, name: payload.email.split("@")[0] } });
      return true;
    } catch {
      return false;
    }
  },
  logout: () => {
    localStorage.removeItem("token");
    set({ token: null, user: null });
  },
  loadToken: () => {
    const token = localStorage.getItem("token");
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split(".")[1]));
        set({ token, user: { email: payload.email, role: payload.role, name: payload.email.split("@")[0] } });
      } catch {
        localStorage.removeItem("token");
      }
    }
  },
}));
