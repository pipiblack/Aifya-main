"use client";

import { useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import { generateId } from "@/lib/utils";
import type {
  Encounter,
  EncounterCreate,
  EncounterUpdate,
  QueueResponse,
  VitalSign,
  VitalSignCreate,
  Diagnosis,
  DiagnosisCreate,
  Prescription,
  PrescriptionCreate,
  PrescriptionWithInteractions,
  LabOrder,
  LabOrderCreate,
} from "@aifya/shared";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

// ── Encounter hooks ──────────────────────────────────────────────────────

/**
 * Hook for fetching the OPD queue with offline support.
 *
 * @param statusFilter - Optional status filter
 * @returns Query result with queue data
 */
export function useOPDQueue(statusFilter?: string) {
  const params: Record<string, string> = {};
  if (statusFilter) {
    params["status"] = statusFilter;
  }

  return useOfflineQuery<QueueResponse>({
    queryKey: ["encounters", "queue", statusFilter ?? ""],
    queryFn: () => apiClient.get<QueueResponse>("/encounters/queue", params),
    refetchInterval: 15_000,
  });
}

/**
 * Hook for fetching a single encounter by ID.
 *
 * @param encounterId - Encounter UUID
 * @returns Query result with encounter data
 */
export function useEncounter(encounterId: string) {
  return useOfflineQuery<Encounter>({
    queryKey: ["encounters", encounterId],
    queryFn: () => apiClient.get<Encounter>(`/encounters/${encounterId}`),
    enabled: !!encounterId,
  });
}

/**
 * Hook for creating a new encounter with offline queue support.
 *
 * @returns Mutation for creating an encounter
 */
export function useCreateEncounter() {
  const queryClient = useQueryClient();

  return useOfflineMutation<Encounter, EncounterCreate>(
    {
      mutationFn: (data: EncounterCreate) =>
        apiClient.post<Encounter>("/encounters", data, generateId()),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["encounters"] });
      },
    },
    { url: `${API_URL}/encounters`, method: "POST" }
  );
}

/**
 * Hook for updating an encounter.
 *
 * @param encounterId - Encounter UUID
 * @returns Mutation for updating the encounter
 */
export function useUpdateEncounter(encounterId: string) {
  const queryClient = useQueryClient();

  return useOfflineMutation<Encounter, EncounterUpdate>(
    {
      mutationFn: (data: EncounterUpdate) =>
        apiClient.patch<Encounter>(`/encounters/${encounterId}`, data),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["encounters"] });
      },
    },
    { url: `${API_URL}/encounters/${encounterId}`, method: "PATCH" }
  );
}

/**
 * Hook for calling the next patient in the OPD queue.
 *
 * @returns Mutation for calling next patient
 */
export function useCallNext() {
  const queryClient = useQueryClient();

  return useOfflineMutation<Encounter, void>(
    {
      mutationFn: () =>
        apiClient.post<Encounter>("/encounters/queue/call-next", {}),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["encounters"] });
      },
    },
    { url: `${API_URL}/encounters/queue/call-next`, method: "POST" }
  );
}

// ── Vitals hooks ─────────────────────────────────────────────────────────

/**
 * Hook for fetching vitals for an encounter.
 *
 * @param encounterId - Encounter UUID
 * @returns Query result with vitals
 */
export function useEncounterVitals(encounterId: string) {
  return useOfflineQuery<VitalSign[]>({
    queryKey: ["encounters", encounterId, "vitals"],
    queryFn: () =>
      apiClient.get<VitalSign[]>(`/encounters/${encounterId}/vitals`),
    enabled: !!encounterId,
  });
}

/**
 * Hook for recording vital signs.
 *
 * @param encounterId - Encounter UUID
 * @returns Mutation for recording vitals
 */
export function useRecordVitals(encounterId: string) {
  const queryClient = useQueryClient();

  return useOfflineMutation<VitalSign, VitalSignCreate>(
    {
      mutationFn: (data: VitalSignCreate) =>
        apiClient.post<VitalSign>(
          `/encounters/${encounterId}/vitals`,
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["encounters", encounterId, "vitals"],
        });
      },
    },
    { url: `${API_URL}/encounters/${encounterId}/vitals`, method: "POST" }
  );
}

// ── Diagnosis hooks ──────────────────────────────────────────────────────

/**
 * Hook for fetching diagnoses for an encounter.
 *
 * @param encounterId - Encounter UUID
 * @returns Query result with diagnoses
 */
export function useEncounterDiagnoses(encounterId: string) {
  return useOfflineQuery<Diagnosis[]>({
    queryKey: ["encounters", encounterId, "diagnoses"],
    queryFn: () =>
      apiClient.get<Diagnosis[]>(`/encounters/${encounterId}/diagnoses`),
    enabled: !!encounterId,
  });
}

/**
 * Hook for adding a diagnosis.
 *
 * @param encounterId - Encounter UUID
 * @returns Mutation for adding diagnosis
 */
export function useAddDiagnosis(encounterId: string) {
  const queryClient = useQueryClient();

  return useOfflineMutation<Diagnosis, DiagnosisCreate>(
    {
      mutationFn: (data: DiagnosisCreate) =>
        apiClient.post<Diagnosis>(
          `/encounters/${encounterId}/diagnoses`,
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["encounters", encounterId, "diagnoses"],
        });
      },
    },
    { url: `${API_URL}/encounters/${encounterId}/diagnoses`, method: "POST" }
  );
}

// ── Prescription hooks ───────────────────────────────────────────────────

/**
 * Hook for fetching prescriptions for an encounter.
 *
 * @param encounterId - Encounter UUID
 * @returns Query result with prescriptions
 */
export function useEncounterPrescriptions(encounterId: string) {
  return useOfflineQuery<Prescription[]>({
    queryKey: ["encounters", encounterId, "prescriptions"],
    queryFn: () =>
      apiClient.get<Prescription[]>(
        `/encounters/${encounterId}/prescriptions`
      ),
    enabled: !!encounterId,
  });
}

/**
 * Hook for creating a prescription with interaction checking.
 *
 * @param encounterId - Encounter UUID
 * @returns Mutation for creating prescription
 */
export function useCreatePrescription(encounterId: string) {
  const queryClient = useQueryClient();

  return useOfflineMutation<PrescriptionWithInteractions, PrescriptionCreate>(
    {
      mutationFn: (data: PrescriptionCreate) =>
        apiClient.post<PrescriptionWithInteractions>(
          `/encounters/${encounterId}/prescriptions`,
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["encounters", encounterId, "prescriptions"],
        });
      },
    },
    {
      url: `${API_URL}/encounters/${encounterId}/prescriptions`,
      method: "POST",
    }
  );
}

// ── Lab Order hooks ──────────────────────────────────────────────────────

/**
 * Hook for fetching lab orders for an encounter.
 *
 * @param encounterId - Encounter UUID
 * @returns Query result with lab orders
 */
export function useEncounterLabOrders(encounterId: string) {
  return useOfflineQuery<LabOrder[]>({
    queryKey: ["encounters", encounterId, "lab-orders"],
    queryFn: () =>
      apiClient.get<LabOrder[]>(`/encounters/${encounterId}/lab-orders`),
    enabled: !!encounterId,
  });
}

/**
 * Hook for creating a lab order.
 *
 * @param encounterId - Encounter UUID
 * @returns Mutation for creating lab order
 */
export function useCreateLabOrder(encounterId: string) {
  const queryClient = useQueryClient();

  return useOfflineMutation<LabOrder, LabOrderCreate>(
    {
      mutationFn: (data: LabOrderCreate) =>
        apiClient.post<LabOrder>(
          `/encounters/${encounterId}/lab-orders`,
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["encounters", encounterId, "lab-orders"],
        });
      },
    },
    {
      url: `${API_URL}/encounters/${encounterId}/lab-orders`,
      method: "POST",
    }
  );
}
