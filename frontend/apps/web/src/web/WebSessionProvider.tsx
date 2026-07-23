import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";

import { getSession, login as apiLogin, logoutWebSession, WebApiError } from "./api";
import type { WebSession } from "./types";

type WebSessionStatus = "loading" | "ready" | "error";

export interface WebSessionContextValue {
  status: WebSessionStatus;
  session: WebSession | null;
  login(employeeCode: string, pin: string): Promise<WebSession>;
  logout(): Promise<void>;
  refresh(): Promise<WebSession | null>;
}

const WebSessionContext = createContext<WebSessionContextValue | null>(null);

export function WebSessionProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<WebSessionStatus>("loading");
  const [session, setSession] = useState<WebSession | null>(null);

  const refresh = useCallback(async (): Promise<WebSession | null> => {
    try {
      const data = await getSession();
      setSession(data);
      setStatus("ready");
      return data;
    } catch (cause) {
      if (cause instanceof WebApiError && cause.status === 401) {
        setSession(null);
        setStatus("ready");
        return null;
      }
      setStatus("error");
      return null;
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(
    async (employeeCode: string, pin: string): Promise<WebSession> => {
      const data = await apiLogin(employeeCode, pin);
      setSession(data);
      setStatus("ready");
      return data;
    },
    [],
  );

  const logout = useCallback(async (): Promise<void> => {
    await logoutWebSession();
    setSession(null);
    setStatus("ready");
  }, []);

  const value = useMemo<WebSessionContextValue>(
    () => ({ status, session, login, logout, refresh }),
    [status, session, login, logout, refresh],
  );

  return (
    <WebSessionContext.Provider value={value}>
      {children}
    </WebSessionContext.Provider>
  );
}

export function useWebSession(): WebSessionContextValue {
  const ctx = useContext(WebSessionContext);
  if (!ctx) {
    throw new Error("useWebSession must be used inside WebSessionProvider");
  }
  return ctx;
}
