"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

/**
 * Keycloak OIDC callback page (legacy redirect).
 * The actual token exchange now happens server-side at /next-api/auth/callback.
 * This page handles cases where the redirect URI still points here.
 *
 * @returns Loading state while redirecting
 */
export default function AuthCallbackPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const code = searchParams.get("code");
    if (code) {
      // Redirect to server-side handler which sets httpOnly cookies
      window.location.href = `/next-api/auth/callback?code=${encodeURIComponent(code)}`;
    } else {
      router.push("/");
    }
  }, [searchParams, router]);

  return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <p className="text-muted-foreground">Authenticating...</p>
    </div>
  );
}
