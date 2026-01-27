export function getGatewayBaseUrl(): string {
  const fromEnv = process.env.NEXT_PUBLIC_GATEWAY_URL;
  if (typeof window === "undefined") {
    return fromEnv || "http://localhost:8080";
  }
  // If env is not set or points to localhost (bad for LAN access), derive from current host.
  if (!fromEnv || fromEnv.includes("localhost") || fromEnv.includes("127.0.0.1")) {
    return `${window.location.protocol}//${window.location.hostname}:8080`;
  }
  return fromEnv;
}

