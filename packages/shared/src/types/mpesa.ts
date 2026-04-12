/**
 * M-Pesa Daraja integration types.
 * STK Push payments, callbacks, and transaction tracking.
 */

/** STK Push payment request. */
export interface STKPushApiRequest {
  phone_number: string;
  amount_kes: number;
  invoice_id: string;
  description?: string;
}

/** STK Push API response. */
export interface STKPushResponse {
  merchant_request_id: string;
  checkout_request_id: string;
  response_code: string;
  response_description: string;
  customer_message: string;
  success: boolean;
  error: string | null;
}

/** Transaction status query result. */
export interface MPesaTransactionStatus {
  result_code: number;
  result_desc: string;
  receipt_number: string | null;
}

/** M-Pesa configuration status. */
export interface MPesaStatus {
  configured: boolean;
  environment: string;
  shortcode: string;
}
