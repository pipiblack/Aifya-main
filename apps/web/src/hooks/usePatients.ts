"use client";

import { useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import type {
  Patient,
  PatientListResponse,
  PatientCreate,
} from "@aifya/shared";
import { generateId } from "@/lib/utils";

/** Partial patient payload accepted by PATCH /patients/{id}. */
export type PatientUpdatePayload = Partial<Omit<PatientCreate, "allergies" | "chronic_conditions">> & {
  allergies?: string[] | null;
  chronic_conditions?: string[] | null;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

/**
 * Hook for searching and listing patients with offline support.
 *
 * @param query - Search string
 * @param page - Page number
 * @param pageSize - Results per page
 * @returns Query result with patient list
 */
export function usePatientSearch(
  query?: string,
  page: number = 1,
  pageSize: number = 20
) {
  const params: Record<string, string> = {
    page: String(page),
    page_size: String(pageSize),
  };
  if (query) {
    params["q"] = query;
  }

  return useOfflineQuery<PatientListResponse>({
    queryKey: ["patients", "search", query ?? "", page, pageSize],
    queryFn: () => apiClient.get<PatientListResponse>("/patients", params),
  });
}

/**
 * Hook for fetching a single patient by ID with offline support.
 *
 * @param patientId - Patient UUID
 * @returns Query result with patient data
 */
export function usePatient(patientId: string) {
  return useOfflineQuery<Patient>({
    queryKey: ["patients", patientId],
    queryFn: () => apiClient.get<Patient>(`/patients/${patientId}`),
    enabled: !!patientId,
  });
}

/**
 * Hook for registering a new patient with offline queue support.
 *
 * @returns Mutation for creating a patient
 */
export function useRegisterPatient() {
  const queryClient = useQueryClient();

  return useOfflineMutation<Patient, PatientCreate>(
    {
      mutationFn: (data: PatientCreate) =>
        apiClient.post<Patient>("/patients", data, generateId()),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["patients"] });
      },
    },
    { url: `${API_URL}/patients`, method: "POST" }
  );
}

/**
 * Hook for updating an existing patient (admin-only on the backend).
 * Audit (2026-05-14): patient edits gated by admin/facility_admin/records_admin
 * roles; backend rejects with 403 if caller lacks the role.
 *
 * @param patientId - Patient UUID being edited
 * @returns Mutation for updating a patient
 */
export function useUpdatePatient(patientId: string) {
  const queryClient = useQueryClient();

  return useOfflineMutation<Patient, PatientUpdatePayload>(
    {
      mutationFn: (data: PatientUpdatePayload) =>
        apiClient.patch<Patient>(`/patients/${patientId}`, data, generateId()),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["patients", patientId] });
        queryClient.invalidateQueries({ queryKey: ["patients"] });
      },
    },
    { url: `${API_URL}/patients/${patientId}`, method: "PATCH" }
  );
}
