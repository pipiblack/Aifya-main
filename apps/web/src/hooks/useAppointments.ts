"use client";

import { useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import { generateId } from "@/lib/utils";
import type {
  AppointmentSummary,
  AppointmentListResponse,
  AppointmentResponse,
  AppointmentCreate,
  AppointmentUpdate,
  AppointmentCheckIn,
  DoctorScheduleResponse,
  DoctorScheduleCreate,
  AvailableSlot,
} from "@aifya/shared";

// ── Summary ────────────────────────────────────────────────────────────────

/**
 * Hook for fetching appointment dashboard summary.
 *
 * @returns Query result with today's appointment summary stats
 */
export function useAppointmentSummary() {
  return useOfflineQuery<AppointmentSummary>({
    queryKey: ["appointments", "summary"],
    queryFn: () => apiClient.get<AppointmentSummary>("/appointments/summary"),
    refetchInterval: 30_000,
  });
}

// ── Doctor Schedules ───────────────────────────────────────────────────────

/**
 * Hook for fetching doctor schedules.
 *
 * @param doctorId - Optional doctor UUID filter
 * @returns Query result with doctor schedules
 */
export function useDoctorSchedules(doctorId?: string) {
  const params = new URLSearchParams();
  if (doctorId) params.set("doctor_id", doctorId);
  const qs = params.toString();

  return useOfflineQuery<DoctorScheduleResponse[]>({
    queryKey: ["appointments", "schedules", doctorId],
    queryFn: () =>
      apiClient.get<DoctorScheduleResponse[]>(
        `/appointments/schedules${qs ? `?${qs}` : ""}`
      ),
    refetchInterval: 30_000,
  });
}

/**
 * Hook for creating a doctor schedule.
 *
 * @returns Mutation for creating a schedule
 */
export function useCreateSchedule() {
  const qc = useQueryClient();
  return useOfflineMutation<DoctorScheduleResponse, DoctorScheduleCreate>({
    mutationFn: (data) =>
      apiClient.post<DoctorScheduleResponse>("/appointments/schedules", data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["appointments", "schedules"] });
    },
    offlineKey: "create-schedule",
    generateOfflineId: generateId,
  });
}

// ── Available Slots ────────────────────────────────────────────────────────

/**
 * Hook for fetching available appointment slots.
 *
 * @param date - Date to check availability (YYYY-MM-DD)
 * @param doctorId - Optional doctor UUID filter
 * @returns Query result with available slots
 */
export function useAvailableSlots(date?: string, doctorId?: string) {
  const params = new URLSearchParams();
  if (date) params.set("date", date);
  if (doctorId) params.set("doctor_id", doctorId);
  const qs = params.toString();

  return useOfflineQuery<AvailableSlot[]>({
    queryKey: ["appointments", "slots", date, doctorId],
    queryFn: () =>
      apiClient.get<AvailableSlot[]>(
        `/appointments/slots${qs ? `?${qs}` : ""}`
      ),
    enabled: !!date,
  });
}

// ── Appointments ───────────────────────────────────────────────────────────

/**
 * Hook for fetching appointment list.
 *
 * @param date - Optional date filter (YYYY-MM-DD)
 * @param doctorId - Optional doctor UUID filter
 * @param patientId - Optional patient UUID filter
 * @param status - Optional status filter
 * @returns Query result with appointment list
 */
export function useAppointmentList(
  date?: string,
  doctorId?: string,
  patientId?: string,
  status?: string
) {
  const params = new URLSearchParams();
  if (date) params.set("date", date);
  if (doctorId) params.set("doctor_id", doctorId);
  if (patientId) params.set("patient_id", patientId);
  if (status) params.set("status", status);
  const qs = params.toString();

  return useOfflineQuery<AppointmentListResponse>({
    queryKey: ["appointments", "list", date, doctorId, patientId, status],
    queryFn: () =>
      apiClient.get<AppointmentListResponse>(
        `/appointments${qs ? `?${qs}` : ""}`
      ),
    refetchInterval: 15_000,
  });
}

/**
 * Hook for fetching a single appointment detail.
 *
 * @param appointmentId - Appointment UUID
 * @returns Query result with appointment detail
 */
export function useAppointmentDetail(appointmentId?: string) {
  return useOfflineQuery<AppointmentResponse>({
    queryKey: ["appointments", "detail", appointmentId],
    queryFn: () =>
      apiClient.get<AppointmentResponse>(`/appointments/${appointmentId}`),
    enabled: !!appointmentId,
  });
}

/**
 * Hook for creating an appointment.
 *
 * @returns Mutation for booking an appointment
 */
export function useCreateAppointment() {
  const qc = useQueryClient();
  return useOfflineMutation<AppointmentResponse, AppointmentCreate>({
    mutationFn: (data) =>
      apiClient.post<AppointmentResponse>("/appointments", data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["appointments"] });
    },
    offlineKey: "create-appointment",
    generateOfflineId: generateId,
  });
}

/**
 * Hook for updating an appointment (reschedule, cancel, change status).
 *
 * @param appointmentId - Appointment UUID
 * @returns Mutation for updating the appointment
 */
export function useUpdateAppointment(appointmentId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<AppointmentResponse, AppointmentUpdate>({
    mutationFn: (data) =>
      apiClient.patch<AppointmentResponse>(
        `/appointments/${appointmentId}`,
        data
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["appointments"] });
    },
    offlineKey: `update-appointment-${appointmentId}`,
    generateOfflineId: generateId,
  });
}

/**
 * Hook for checking in a patient for their appointment.
 *
 * @param appointmentId - Appointment UUID
 * @returns Mutation for check-in
 */
export function useCheckInAppointment(appointmentId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<AppointmentResponse, AppointmentCheckIn>({
    mutationFn: (data) =>
      apiClient.post<AppointmentResponse>(
        `/appointments/${appointmentId}/check-in`,
        data
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["appointments"] });
    },
    offlineKey: `checkin-appointment-${appointmentId}`,
    generateOfflineId: generateId,
  });
}
