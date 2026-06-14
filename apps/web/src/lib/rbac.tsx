"use client";

import { useAuth } from "@/components/providers/AuthProvider";
import { StaffRole } from "@aifya/shared/src/types/hr";
import { ReactNode } from "react";

/**
 * Hook to check if the current user has required roles
 */
export function useRBAC() {
    const { user, isAuthenticated, isLoading } = useAuth();

    const hasRole = (roles: StaffRole | StaffRole[]) => {
        if (!isAuthenticated || !user) return false;

        // Keycloak maps roles as strings; we check intersection
        const requiredRoles = Array.isArray(roles) ? roles : [roles];
        return requiredRoles.some((role) => user.roles.includes(role));
    };

    const hasAnyRole = (roles: StaffRole[]) => {
        if (!isAuthenticated || !user) return false;
        return roles.some((role) => user.roles.includes(role));
    };

    const hasAllRoles = (roles: StaffRole[]) => {
        if (!isAuthenticated || !user) return false;
        return roles.every((role) => user.roles.includes(role));
    };

    return {
        hasRole,
        hasAnyRole,
        hasAllRoles,
        isSuperAdmin: () => hasRole("system_admin"),
        isLoading
    };
}

/**
 * A wrapper component to conditionally render parts of the UI based on roles
 */
export function RoleProtect({
    children,
    allowedRoles,
    fallback = null
}: {
    children: ReactNode;
    allowedRoles: StaffRole | StaffRole[];
    fallback?: ReactNode;
}) {
    const { hasRole, isLoading } = useRBAC();

    if (isLoading) return null; // or a tiny loader

    return hasRole(allowedRoles) ? <>{children}</> : <>{fallback}</>;
}
