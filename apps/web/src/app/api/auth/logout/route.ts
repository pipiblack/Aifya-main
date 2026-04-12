import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const KEYCLOAK_URL = process.env.KEYCLOAK_URL ?? "http://localhost:8080";
const KEYCLOAK_REALM = process.env.KEYCLOAK_REALM ?? "aifya";
const KEYCLOAK_CLIENT_ID = process.env.KEYCLOAK_CLIENT_ID ?? "aifya-web";

/**
 * Server-side logout handler.
 * Clears httpOnly cookies and redirects to Keycloak logout.
 *
 * @param request - Incoming request
 * @returns Redirect to Keycloak logout
 */
export async function GET(request: NextRequest): Promise<NextResponse> {
  const cookieStore = await cookies();

  // Clear auth cookies
  cookieStore.delete("access_token");
  cookieStore.delete("refresh_token");

  const logoutUrl =
    `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}/protocol/openid-connect/logout` +
    `?client_id=${KEYCLOAK_CLIENT_ID}` +
    `&post_logout_redirect_uri=${encodeURIComponent(request.nextUrl.origin)}`;

  return NextResponse.redirect(logoutUrl);
}
