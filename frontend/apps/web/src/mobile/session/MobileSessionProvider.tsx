import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import {
  MobileApiError,
  mobileApiClient,
  type MobileApiClient,
  type MobileSession,
} from "@form-detection/api-client";

import { getMobileDeviceId } from "../device";
import { cleanupSessionStorage } from "../storage/session-cleanup";
import {
  flushPendingOutbox,
  pauseOutboxSync,
  resumeOutboxSync,
} from "../sync/SubmissionCoordinator";

export type MobileSessionStatus = "loading" | "authenticated" | "anonymous" | "error";

export interface MobileSessionContextValue {
  status: MobileSessionStatus;
  sessionMetadata: MobileSession | null;
  error: MobileApiError | Error | null;
  refreshSession(): Promise<MobileSession | null>;
  login(employeeCode: string, pin: string, deviceId?: string): Promise<MobileSession>;
  logout(): Promise<void>;
}

export type MobileSessionClient = Pick<MobileApiClient, "getSession" | "login" | "logout">;

const MobileSessionContext = createContext<MobileSessionContextValue | null>(null);

export function MobileSessionProvider({
  children,
  client = mobileApiClient,
}: {
  children: React.ReactNode;
  client?: MobileSessionClient;
}) {
  const [status, setStatus] = useState<MobileSessionStatus>("loading");
  const [sessionMetadata, setSessionMetadata] = useState<MobileSession | null>(null);
  const [error, setError] = useState<MobileApiError | Error | null>(null);

  const refreshSession = useCallback(async (): Promise<MobileSession | null> => {
    try {
      const session = await client.getSession();
      setSessionMetadata(session);
      setError(null);
      setStatus("authenticated");
      return session;
    } catch (cause) {
      setSessionMetadata(null);
      if (cause instanceof MobileApiError && cause.status === 401) {
        setError(null);
        setStatus("anonymous");
        return null;
      }
      const nextError = cause instanceof Error ? cause : new Error("会话检查失败");
      setError(nextError);
      setStatus("error");
      return null;
    }
  }, [client]);

  useEffect(() => {
    void refreshSession();
  }, [refreshSession]);

  useEffect(() => {
    const handleOnline = () => { void flushPendingOutbox(); };
    window.addEventListener("online", handleOnline);
    return () => window.removeEventListener("online", handleOnline);
  }, []);

  const login = useCallback(async (
    employeeCode: string,
    pin: string,
    deviceId = "unknown",
  ): Promise<MobileSession> => {
    resumeOutboxSync();
    await client.login(employeeCode, pin, deviceId);
    const session = await client.getSession();
    setSessionMetadata(session);
    setError(null);
    setStatus("authenticated");
    void flushPendingOutbox();
    return session;
  }, [client]);

  const logout = useCallback(async (): Promise<void> => {
    const owner = sessionMetadata?.employee_code;
    await pauseOutboxSync();
    try {
      await client.logout();
    } finally {
      if (owner) await cleanupSessionStorage(owner, getMobileDeviceId());
      setSessionMetadata(null);
      setError(null);
      setStatus("anonymous");
    }
  }, [client, sessionMetadata]);

  const value = useMemo<MobileSessionContextValue>(() => ({
    status,
    sessionMetadata,
    error,
    refreshSession,
    login,
    logout,
  }), [error, login, logout, refreshSession, sessionMetadata, status]);

  return <MobileSessionContext.Provider value={value}>{children}</MobileSessionContext.Provider>;
}

export function useMobileSession(): MobileSessionContextValue {
  const value = useContext(MobileSessionContext);
  if (!value) throw new Error("useMobileSession must be used inside MobileSessionProvider");
  return value;
}
