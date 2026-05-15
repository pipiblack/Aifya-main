"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import type {
  InsuranceSchemeListResponse,
  InsuranceSchemeResponse,
  InsuranceSchemeCreate,
  ClaimListResponse,
  ClaimResponse,
  ClaimCreate,
  ClaimStatusUpdate,
  InsuranceSummary,
  PatientInsuranceCreate,
  PatientInsuranceListResponse,
  PatientInsuranceResponse,
  PatientInsuranceUpdate,
} from "@aifya/shared";
import { apiFetch } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

const INS_KEYS = {
  all: ["insurance"] as const,
  summary: () => [...INS_KEYS.all, "summary"] as const,
  schemes: () => [...INS_KEYS.all, "schemes"] as const,
  claims: (status?: string) => [...INS_KEYS.all, "claims", status] as const,
  claim: (id: string) => [...INS_KEYS.all, "claim", id] as const,
  patientInsurances: (patientId: string) =>
    [...INS_KEYS.all, "patient", patientId] as const,
};

/** Get insurance summary. */
export function useInsuranceSummary() {
  return useOfflineQuery<InsuranceSummary>({
    queryKey: INS_KEYS.summary(),
    queryFn: () => apiFetch("/api/v1/insurance/summary"),
    staleTime: 30_000,
  });
}

/** Get insurance schemes. */
export function useInsuranceSchemes() {
  return useOfflineQuery<InsuranceSchemeListResponse>({
    queryKey: INS_KEYS.schemes(),
    queryFn: () => apiFetch("/api/v1/insurance/schemes"),
    staleTime: 60_000,
  });
}

/** Create insurance scheme. */
export function useCreateScheme() {
  const qc = useQueryClient();
  return useOfflineMutation<InsuranceSchemeResponse, InsuranceSchemeCreate>(
    {
      mutationFn: (data) => apiFetch("/api/v1/insurance/schemes", { method: "POST", body: JSON.stringify(data) }),
      onSuccess: () => qc.invalidateQueries({ queryKey: INS_KEYS.schemes() }),
    },
    { url: `${API_URL}/insurance/schemes`, method: "POST" }
  );
}

/** Get insurance claims. */
export function useInsuranceClaims(status?: string) {
  const params = status ? `?status=${status}` : "";
  return useOfflineQuery<ClaimListResponse>({
    queryKey: INS_KEYS.claims(status),
    queryFn: () => apiFetch(`/api/v1/insurance/claims${params}`),
    staleTime: 30_000,
  });
}

/** Get a single insurance claim. */
export function useInsuranceClaim(id: string) {
  return useOfflineQuery<ClaimResponse>({
    queryKey: INS_KEYS.claim(id),
    queryFn: () => apiFetch(`/api/v1/insurance/claims/${id}`),
    enabled: !!id,
  });
}

/** Create insurance claim. */
export function useCreateClaim() {
  const qc = useQueryClient();
  return useOfflineMutation<ClaimResponse, ClaimCreate>(
    {
      mutationFn: (data) => apiFetch("/api/v1/insurance/claims", { method: "POST", body: JSON.stringify(data) }),
      onSuccess: () => qc.invalidateQueries({ queryKey: INS_KEYS.all }),
    },
    { url: `${API_URL}/insurance/claims`, method: "POST" }
  );
}

/** Update claim status. */
export function useUpdateClaimStatus(id: string) {
  const qc = useQueryClient();
  return useOfflineMutation<ClaimResponse, ClaimStatusUpdate>(
    {
      mutationFn: (data) => apiFetch(`/api/v1/insurance/claims/${id}/status`, { method: "POST", body: JSON.stringify(data) }),
      onSuccess: () => qc.invalidateQueries({ queryKey: INS_KEYS.all }),
    },
    { url: `${API_URL}/insurance/claims/${id}/status`, method: "POST" }
  );
}

// ── Patient insurance (multi-entry) ──────────────────────────────────────────

/**
 * List all insurance entries for a patient. Returns the primary entry first,
 * then any secondary insurers. Supports multiple insurers per patient
 * (e.g. SHA + private) per the 2026-05-14 audit.
 */
export function usePatientInsurances(patientId: string) {
  return useOfflineQuery<PatientInsuranceListResponse>({
    queryKey: INS_KEYS.patientInsurances(patientId),
    queryFn: () => apiFetch(`/api/v1/patients/${patientId}/insurances`),
    enabled: !!patientId,
    staleTime: 30_000,
  });
}

/** Add a new insurance entry for a patient. */
export function useAddPatientInsurance(patientId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<PatientInsuranceResponse, PatientInsuranceCreate>(
    {
      mutationFn: (data) =>
        apiFetch(`/api/v1/patients/${patientId}/insurances`, {
          method: "POST",
          body: JSON.stringify(data),
        }),
      onSuccess: () => {
        qc.invalidateQueries({
          queryKey: INS_KEYS.patientInsurances(patientId),
        });
        qc.invalidateQueries({ queryKey: ["patients", patientId] });
      },
    },
    { url: `${API_URL}/patients/${patientId}/insurances`, method: "POST" }
  );
}

/** Edit a patient insurance entry. */
export function useUpdatePatientInsurance(patientId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<
    PatientInsuranceResponse,
    { insuranceId: string; data: PatientInsuranceUpdate }
  >(
    {
      mutationFn: ({ insuranceId, data }) =>
        apiFetch(
          `/api/v1/patients/${patientId}/insurances/${insuranceId}`,
          { method: "PATCH", body: JSON.stringify(data) }
        ),
      onSuccess: () => {
        qc.invalidateQueries({
          queryKey: INS_KEYS.patientInsurances(patientId),
        });
        qc.invalidateQueries({ queryKey: ["patients", patientId] });
      },
    },
    {
      url: `${API_URL}/patients/${patientId}/insurances/_`,
      method: "PATCH",
    }
  );
}

/** Soft-delete a patient insurance entry. */
export function useDeletePatientInsurance(patientId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<void, { insuranceId: string }>(
    {
      mutationFn: ({ insuranceId }) =>
        apiFetch(
          `/api/v1/patients/${patientId}/insurances/${insuranceId}`,
          { method: "DELETE" }
        ),
      onSuccess: () => {
        qc.invalidateQueries({
          queryKey: INS_KEYS.patientInsurances(patientId),
        });
        qc.invalidateQueries({ queryKey: ["patients", patientId] });
      },
    },
    {
      url: `${API_URL}/patients/${patientId}/insurances/_`,
      method: "DELETE",
    }
  );
}

/** Promote a patient insurance entry to primary. */
export function useSetPrimaryPatientInsurance(patientId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<
    PatientInsuranceResponse,
    { insuranceId: string }
  >(
    {
      mutationFn: ({ insuranceId }) =>
        apiFetch(
          `/api/v1/patients/${patientId}/insurances/${insuranceId}/set-primary`,
          { method: "POST" }
        ),
      onSuccess: () => {
        qc.invalidateQueries({
          queryKey: INS_KEYS.patientInsurances(patientId),
        });
        qc.invalidateQueries({ queryKey: ["patients", patientId] });
      },
    },
    {
      url: `${API_URL}/patients/${patientId}/insurances/_/set-primary`,
      method: "POST",
    }
  );
}

// ── ClaimFlow integration ──────────────────────────────────────────────────

/** Response shape from ClaimFlow action endpoints. */
export interface ClaimFlowActionResponse {
  ok: boolean;
  claim_id: string;
  local_status?: string;
  claimflow_external_id?: string | null;
  claimflow_status?: string | null;
  approved_amount?: number;
  paid_amount?: number;
  view_url?: string | null;
  details?: Record<string, unknown>;
}

/** Submit a claim to ClaimFlow. */
export function useSubmitClaimToClaimFlow(claimId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<ClaimFlowActionResponse, void>(
    {
      mutationFn: () =>
        apiFetch(`/api/v1/insurance/claims/${claimId}/submit-to-claimflow`, {
          method: "POST",
        }),
      onSuccess: () => qc.invalidateQueries({ queryKey: INS_KEYS.all }),
    },
    {
      url: `${API_URL}/insurance/claims/${claimId}/submit-to-claimflow`,
      method: "POST",
    },
  );
}

/** Sync a claim's status from ClaimFlow into Aifya. */
export function useSyncClaimWithClaimFlow(claimId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<ClaimFlowActionResponse, void>(
    {
      mutationFn: () =>
        apiFetch(`/api/v1/insurance/claims/${claimId}/sync-with-claimflow`, {
          method: "POST",
        }),
      onSuccess: () => qc.invalidateQueries({ queryKey: INS_KEYS.all }),
    },
    {
      url: `${API_URL}/insurance/claims/${claimId}/sync-with-claimflow`,
      method: "POST",
    },
  );
}

/** Read-only fetch of latest ClaimFlow status. */
export function useClaimFlowStatus(claimId: string, enabled = true) {
  return useOfflineQuery<ClaimFlowActionResponse>({
    queryKey: [...INS_KEYS.claim(claimId), "claimflow-status"],
    queryFn: () =>
      apiFetch(`/api/v1/insurance/claims/${claimId}/claimflow-status`),
    enabled: enabled && !!claimId,
    staleTime: 15_000,
  });
}
