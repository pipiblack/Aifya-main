import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const KEYCLOAK_URL = process.env.KEYCLOAK_URL ?? "http://localhost:8080";
const KEYCLOAK_REALM = process.env.KEYCLOAK_REALM ?? "aifya";
const KEYCLOAK_CLIENT_ID = process.env.KEYCLOAK_CLIENT_ID ?? "aifya-web";
const KEYCLOAK_CLIENT_SECRET = process.env.KEYCLOAK_CLIENT_SECRET ?? "";

/**
 * Server-side OIDC callback handler.
 * Exchanges authorization code for tokens and sets httpOnly cookies.
 * Tokens NEVER reach client JavaScript — prevents XSS token theft.
 *
 * @param request - Incoming request with ?code= query param
 * @returns Redirect to home page
 */
export async function GET(request: NextRequest): Promise<NextResponse> {
  const code = request.nextUrl.searchParams.get("code");
  if (!code) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  const tokenUrl = `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}/protocol/openid-connect/token`;
  const redirectUri = `${request.nextUrl.origin}/next-api/auth/callback`;

  const body = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: KEYCLOAK_CLIENT_ID,
    code,
    redirect_uri: redirectUri,
  });

  // Include client secret if configured (confidential client)
  if (KEYCLOAK_CLIENT_SECRET) {
    body.set("client_secret", KEYCLOAK_CLIENT_SECRET);
  }

  try {
    const response = await fetch(tokenUrl, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });

    if (!response.ok) {
      return NextResponse.redirect(new URL("/", request.url));
    }

    const data = await response.json();
    const cookieStore = await cookies();

    // Set access token as httpOnly cookie — not accessible from JS
    cookieStore.set("access_token", data.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: data.expires_in ?? 300,
    });

    // Set refresh token as httpOnly cookie for silent renewal
    if (data.refresh_token) {
      cookieStore.set("refresh_token", data.refresh_token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        path: "/",
        maxAge: data.refresh_expires_in ?? 1800,
      });
    }

    return NextResponse.redirect(new URL("/", request.url));
  } catch {
    return NextResponse.redirect(new URL("/", request.url));
  }
}
