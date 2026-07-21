export type RuntimeCachePolicy = "NetworkOnly" | null;

const PRIVATE_OR_MUTABLE_PATH = /(?:^\/api\/|^\/evidence\/|^\/downloads\/|\/download(?:\/|$)|\.(?:xlsx|xls|csv|pdf|zip)$)/i;

/** Private and mutable data is never served from the Service Worker cache. */
export function runtimePolicyForPath(pathname: string): RuntimeCachePolicy {
  return PRIVATE_OR_MUTABLE_PATH.test(pathname) ? "NetworkOnly" : null;
}
