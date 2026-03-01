"use client";

import { useRouter } from "next/navigation";
import React, { useEffect, useState } from "react";

type Props = {
  children: React.ReactNode;
};

export default function KeycloakGate({ children }: Props) {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        // MVP: server-side callback sets cookie sonya_session=<id>.
        // If it's missing, send user to /signin.
        const hasSession =
          typeof document !== "undefined" &&
          document.cookie.split(";").some((c) => c.trim().startsWith("sonya_session_present="));

        if (!hasSession) {
          router.push("/signin");
          return;
        }

        setReady(true);
      } catch (e: any) {
        setError(e?.message || "Keycloak init failed");
        // fallback: go to template signin page
        router.push("/signin");
      }
    })();
  }, [router]);

  if (error) {
    return (
      <div className="p-6">
        <div className="text-red-600 font-medium">Auth error</div>
        <div className="text-sm text-gray-600 mt-2">{error}</div>
      </div>
    );
  }

  if (!ready) {
    return (
      <div className="p-6">
        <div className="text-sm text-gray-600">Signing you in...</div>
      </div>
    );
  }

  return <>{children}</>;
}


