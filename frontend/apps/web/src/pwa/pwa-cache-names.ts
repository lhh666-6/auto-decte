export const PWA_CACHE_PREFIX = "form-detection-web";
export const PWA_CACHE_VERSION = "v3";
export const PWA_CACHE_ID = `${PWA_CACHE_PREFIX}-${PWA_CACHE_VERSION}`;

export function isOwnedPwaCache(cacheName: string): boolean {
  return cacheName === PWA_CACHE_PREFIX || cacheName.startsWith(`${PWA_CACHE_PREFIX}-`);
}
