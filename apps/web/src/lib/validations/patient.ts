import { z } from "zod";

/** Zod schema for patient registration form validation. */
export const patientCreateSchema = z.object({
  first_name: z.string().min(1).max(100),
  middle_name: z.string().max(100).nullable().optional(),
  last_name: z.string().min(1).max(100),
  date_of_birth: z.string().min(1),
  gender: z.enum(["male", "female", "other"]),
  national_id: z.string().max(50).nullable().optional(),
  passport_number: z.string().max(50).nullable().optional(),
  phone_number: z.string().min(9).max(20),
  alternate_phone: z.string().max(20).nullable().optional(),
  email: z.string().email().max(255).nullable().optional().or(z.literal("")),
  county: z.string().max(100).nullable().optional(),
  sub_county: z.string().max(100).nullable().optional(),
  ward: z.string().max(100).nullable().optional(),
  village: z.string().max(200).nullable().optional(),
  postal_address: z.string().max(200).nullable().optional(),
  occupation: z.string().max(100).nullable().optional(),
  marital_status: z.enum(["single", "married", "divorced", "widowed"]).nullable().optional(),
  next_of_kin_name: z.string().max(200).nullable().optional(),
  next_of_kin_phone: z.string().max(20).nullable().optional(),
  next_of_kin_relationship: z.string().max(50).nullable().optional(),
  insurance_provider: z.string().max(100).nullable().optional(),
  insurance_member_number: z.string().max(100).nullable().optional(),
  sha_number: z.string().max(50).nullable().optional(),
  blood_group: z.string().regex(/^(A|B|AB|O)[+-]$/).nullable().optional().or(z.literal("")),
  allergies: z.array(z.string()).nullable().optional(),
  chronic_conditions: z.array(z.string()).nullable().optional(),
});

export type PatientCreateFormData = z.infer<typeof patientCreateSchema>;
