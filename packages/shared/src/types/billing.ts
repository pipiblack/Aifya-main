/** Invoice status lifecycle. */
export type InvoiceStatus =
  | "draft"
  | "finalized"
  | "partially_paid"
  | "paid"
  | "cancelled"
  | "waived";

/** Payment method options. */
export type PaymentMethod = "cash" | "mpesa" | "insurance" | "exemption";

/** Invoice line item type. */
export type InvoiceItemType =
  | "consultation"
  | "pharmacy"
  | "lab"
  | "procedure"
  | "bed"
  | "nursing"
  | "other";

// ── Invoice ──────────────────────────────────────────────────────────────────

/** Invoice response from the API. */
export interface InvoiceResponse {
  id: string;
  encounter_id: string;
  patient_id: string;
  invoice_number: string;
  status: InvoiceStatus;
  payment_method: PaymentMethod | null;
  insurance_provider: string | null;
  insurance_member_no: string | null;
  sha_claim_ref: string | null;
  subtotal_cents: number;
  discount_cents: number;
  tax_cents: number;
  total_cents: number;
  paid_cents: number;
  balance_cents: number;
  notes: string | null;
  finalized_at: string | null;
  created_at: string;
}

/** Invoice line item response. */
export interface InvoiceItemResponse {
  id: string;
  invoice_id: string;
  item_type: InvoiceItemType;
  description: string;
  quantity: number;
  unit_price_cents: number;
  total_cents: number;
  discount_cents: number;
  reference_id: string | null;
  reference_type: string | null;
}

/** Full invoice with items and patient info. */
export interface InvoiceDetail {
  invoice: InvoiceResponse;
  items: InvoiceItemResponse[];
  patient_name: string | null;
  patient_mrn: string | null;
}

/** Invoice list item (summary). */
export interface InvoiceListItem {
  id: string;
  invoice_number: string;
  encounter_id: string;
  patient_id: string;
  patient_name: string | null;
  patient_mrn: string | null;
  status: InvoiceStatus;
  total_cents: number;
  paid_cents: number;
  balance_cents: number;
  payment_method: PaymentMethod | null;
  item_count: number;
  created_at: string;
}

/** Paginated invoice list. */
export interface InvoiceListResponse {
  items: InvoiceListItem[];
  total: number;
  page: number;
  page_size: number;
}

// ── Invoice Create ───────────────────────────────────────────────────────────

/** Payload for creating a line item. */
export interface InvoiceItemCreate {
  item_type: InvoiceItemType;
  description: string;
  quantity: number;
  unit_price_cents: number;
  discount_cents?: number;
  reference_id?: string | null;
  reference_type?: string | null;
}

/** Payload for creating an invoice. */
export interface InvoiceCreate {
  encounter_id: string;
  patient_id: string;
  payment_method?: PaymentMethod | null;
  insurance_provider?: string | null;
  insurance_member_no?: string | null;
  notes?: string | null;
  items: InvoiceItemCreate[];
}

// ── Payment ──────────────────────────────────────────────────────────────────

/** Payload for recording a payment. */
export interface PaymentCreate {
  amount_cents: number;
  payment_method: PaymentMethod;
  reference_number?: string | null;
  mpesa_transaction_id?: string | null;
  notes?: string | null;
}

/** Payment response from the API. */
export interface PaymentResponseType {
  id: string;
  invoice_id: string;
  patient_id: string;
  amount_cents: number;
  payment_method: PaymentMethod;
  reference_number: string | null;
  mpesa_transaction_id: string | null;
  received_by: string;
  paid_at: string;
  notes: string | null;
}

// ── Dashboard ────────────────────────────────────────────────────────────────

/** Billing dashboard summary. */
export interface BillingSummary {
  total_invoices: number;
  draft_count: number;
  finalized_count: number;
  paid_count: number;
  partially_paid_count: number;
  total_billed_cents: number;
  total_paid_cents: number;
  total_outstanding_cents: number;
}

/** Invoice waiver request. */
export interface InvoiceWaiveRequest {
  reason: string;
}
