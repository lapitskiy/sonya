export function getGatewayBaseUrl(): string {
  const fromEnv = process.env.NEXT_PUBLIC_GATEWAY_URL;
  if (typeof window === "undefined") {
    return fromEnv || "http://localhost:18000";
  }
  // Prefer explicit env, but avoid breaking LAN access:
  // if env points to localhost while UI is opened on a non-localhost host,
  // the browser would try to call its own localhost and fail.
  if (fromEnv) {
    const envIsLocal =
      fromEnv.includes("localhost") || fromEnv.includes("127.0.0.1");
    const browserIsLocal =
      window.location.hostname === "localhost" ||
      window.location.hostname === "127.0.0.1";
    if (!(envIsLocal && !browserIsLocal)) return fromEnv;
  }
  // Derive from current host; API default port in this project is 18000.
  return `${window.location.protocol}//${window.location.hostname}:18000`;
}

