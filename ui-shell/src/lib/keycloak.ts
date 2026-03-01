import Keycloak from "keycloak-js";

let _kc: Keycloak | null = null;
let _initPromise: Promise<boolean> | null = null;

export type KeycloakConfig = {
  url: string;
  realm: string;
  clientId: string;
};

export function getKeycloakConfig(): KeycloakConfig {
  const fromEnv = process.env.NEXT_PUBLIC_KEYCLOAK_URL;
  let url: string;
  if (typeof window === "undefined") {
    url = fromEnv || "http://localhost:18080";
  } else {
    if (fromEnv) {
      const envIsLocal = fromEnv.includes("localhost") || fromEnv.includes("127.0.0.1");
      const browserIsLocal =
        window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
      if (!(envIsLocal && !browserIsLocal)) {
        url = fromEnv;
      } else {
        url = `${window.location.protocol}//${window.location.hostname}:18080`;
      }
    } else {
      url = `${window.location.protocol}//${window.location.hostname}:18080`;
    }
  }
  const realm = process.env.NEXT_PUBLIC_KEYCLOAK_REALM || "sonya";
  const clientId = process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID || "ui-shell";
  return { url, realm, clientId };
}

export function getKeycloak(): Keycloak {
  if (_kc) return _kc;
  const cfg = getKeycloakConfig();
  _kc = new Keycloak(cfg);
  return _kc;
}

export async function ensureKeycloakInit(): Promise<Keycloak> {
  const kc = getKeycloak();
  if (_initPromise) {
    await _initPromise;
    return kc;
  }

  // Check if Web Crypto is available (needed even without PKCE for state/nonce generation)
  const hasWebCrypto =
    typeof window !== "undefined" &&
    typeof window.crypto !== "undefined" &&
    typeof window.crypto.getRandomValues === "function";

  if (!hasWebCrypto) {
    throw new Error(
      "Web Crypto API is not available. Please use HTTPS or open via localhost (SSH tunnel)."
    );
  }

  const canPkce =
    typeof window !== "undefined" && window.isSecureContext && !!window.crypto?.subtle;

  _initPromise = kc.init({
    onLoad: "check-sso",
    checkLoginIframe: false,
    // Disable PKCE if Web Crypto subtle is not available
    ...(canPkce ? { pkceMethod: "S256" } : {}),
  });

  await _initPromise;
  return kc;
}


