import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { getToken, setToken, setUnauthorizedHandler } from "../lib/api";

type AuthState = {
  token: string | null;
  username: string | null;
  login: (token: string, username: string) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

const USERNAME_KEY = "auth_username";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() => getToken());
  const [username, setUsername] = useState<string | null>(() => localStorage.getItem(USERNAME_KEY));

  const logout = useCallback(() => {
    setToken(null);
    localStorage.removeItem(USERNAME_KEY);
    setTokenState(null);
    setUsername(null);
  }, []);

  const login = useCallback((nextToken: string, nextUsername: string) => {
    setToken(nextToken);
    localStorage.setItem(USERNAME_KEY, nextUsername);
    setTokenState(nextToken);
    setUsername(nextUsername);
  }, []);

  useEffect(() => {
    // 任意请求收到 401 时清除登录态，回到登录页。
    setUnauthorizedHandler(() => {
      localStorage.removeItem(USERNAME_KEY);
      setTokenState(null);
      setUsername(null);
    });
  }, []);

  return <AuthContext.Provider value={{ token, username, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
