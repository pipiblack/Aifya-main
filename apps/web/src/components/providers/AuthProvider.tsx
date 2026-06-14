"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";

interface AuthUser {
  id: string;
  email: string;
  name: string;
  roles: string[];
  facilityId: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: () => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  login: () => { },
  logout: () => { },
});

const KEYCLOAK_URL = process.env.NEXT_PUBLIC_KEYCLOAK_URL ?? "http://localhost:8080";
const KEYCLOAK_REALM = process.env.NEXT_PUBLIC_KEYCLOAK_REALM ?? "aifya";
const KEYCLOAK_CLIENT_ID = process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID ?? "aifya-web";

/**
 * Authentication provider using Keycloak OIDC with httpOnly cookies.
 * Tokens are stored in httpOnly cookies set by the server-side callback handler.
 * Client never has direct access to tokens — prevents XSS token theft.
 *
 * @param props.children - Child components
 * @returns Auth context provider
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const login = useCallback(() => {
    // Redirect to Keycloak login — callback goes to server-side Route Handler
    const redirectUri = encodeURIComponent(
      window.location.origin + "/next-api/auth/callback",
    );
    const baseUrl = `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}/protocol/openid-connect`;
    const authUrl =
      `${baseUrl}/auth?client_id=${KEYCLOAK_CLIENT_ID}` +
      `&redirect_uri=${redirectUri}` +
      `&response_type=code` +
      `&scope=openid profile email`;
    window.location.href = authUrl;
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    // Server-side logout handler clears cookies and redirects to Keycloak
    window.location.href = "/next-api/auth/logout";
  }, []);

  // Check session on mount by calling the server-side /api/auth/me endpoint
  useEffect(() => {
    const checkSession = async () => {
      try {
        const response = await fetch("/next-api/auth/me", {
          credentials: "include",
        });
        if (response.ok) {
          const data = await response.json();
          if (data.authenticated && data.user) {
            setUser(data.user);
          }
        }
      } catch {
        // Session check failed — user is not authenticated
      } finally {
        setIsLoading(false);
      }
    };

    checkSession();
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

/**
 * Hook to access auth context.
 *
 * @returns Auth context value
 */
export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}
