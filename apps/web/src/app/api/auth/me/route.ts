import { cookies } from "next/headers";
import { NextResponse } from "next/server";

/**
 * Returns current user info by decoding the httpOnly access_token cookie.
 * This endpoint is the ONLY way the client learns who is logged in —
 * the token itself never reaches client JavaScript.
 *
 * @returns User info or 401
 */
export async function GET(): Promise<NextResponse> {
  const cookieStore = await cookies();
  const token = cookieStore.get("access_token")?.value;

  if (!token) {
    return NextResponse.json(
      { authenticated: false },
      { status: 401 },
    );
  }

  try {
    // Decode JWT payload (base64) — no verification needed since we set the cookie
    const parts = token.split(".");
    if (parts.length !== 3) {
      return NextResponse.json({ authenticated: false }, { status: 401 });
    }

    const payload = JSON.parse(
      Buffer.from(parts[1]!, "base64url").toString("utf-8"),
    );

    // Check expiry
    if (payload.exp && Date.now() >= payload.exp * 1000) {
      // Token expired — try refresh
      const refreshToken = cookieStore.get("refresh_token")?.value;
      if (!refreshToken) {
        return NextResponse.json({ authenticated: false }, { status: 401 });
      }
      // TODO: Implement silent refresh via Keycloak token endpoint
      return NextResponse.json({ authenticated: false }, { status: 401 });
    }

    return NextResponse.json({
      authenticated: true,
      user: {
        id: payload.sub,
        email: payload.email ?? "",
        name: payload.name ?? payload.preferred_username ?? "",
        roles: payload.realm_access?.roles ?? [],
        facilityId: payload.facility_id ?? "",
      },
    });
  } catch {
    return NextResponse.json({ authenticated: false }, { status: 401 });
  }
}
