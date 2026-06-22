const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

interface RequestOptions extends RequestInit {
  params?: Record<string, string>;
}

/**
 * API client for communicating with the FastAPI backend.
 * Handles auth headers, JSON serialization, and idempotency keys.
 */
class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  /**
   * Make an authenticated API request.
   * Uses httpOnly cookies for authentication — tokens never touch JS.
   * @param path - API path (e.g., "/patients")
   * @param options - Fetch options with optional params
   * @returns Parsed JSON response
   */
  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const { params, ...fetchOptions } = options;

    let url = `${this.baseUrl}${path}`;
    if (params) {
      const searchParams = new URLSearchParams(params);
      url += `?${searchParams.toString()}`;
    }

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(fetchOptions.headers as Record<string, string>),
    };

    const response = await fetch(url, {
      ...fetchOptions,
      headers,
      credentials: "include", // Send httpOnly cookies
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        detail: response.statusText,
      }));
      throw new ApiError(response.status, error.detail ?? "Request failed");
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json() as Promise<T>;
  }

  /**
   * GET request.
   * @param path - API path
   * @param params - Query parameters
   * @returns Parsed response
   */
  async get<T>(path: string, params?: Record<string, string>): Promise<T> {
    return this.request<T>(path, { method: "GET", params });
  }

  /**
   * POST request with idempotency key.
   * @param path - API path
   * @param body - Request body
   * @param idempotencyKey - Idempotency key for safe retries
   * @returns Parsed response
   */
  async post<T>(
    path: string,
    body: unknown,
    idempotencyKey?: string
  ): Promise<T> {
    const headers: Record<string, string> = {};
    if (idempotencyKey) {
      headers["X-Idempotency-Key"] = idempotencyKey;
    }
    return this.request<T>(path, {
      method: "POST",
      body: JSON.stringify(body),
      headers,
    });
  }

  /**
   * PATCH request with idempotency key.
   * @param path - API path
   * @param body - Request body
   * @param idempotencyKey - Idempotency key for safe retries
   * @returns Parsed response
   */
  async patch<T>(
    path: string,
    body: unknown,
    idempotencyKey?: string
  ): Promise<T> {
    const headers: Record<string, string> = {};
    if (idempotencyKey) {
      headers["X-Idempotency-Key"] = idempotencyKey;
    }
    return this.request<T>(path, {
      method: "PATCH",
      body: JSON.stringify(body),
      headers,
    });
  }

  /**
   * PUT request with idempotency key.
   * @param path - API path
   * @param body - Request body
   * @param idempotencyKey - Idempotency key for safe retries
   * @returns Parsed response
   */
  async put<T>(
    path: string,
    body: unknown,
    idempotencyKey?: string
  ): Promise<T> {
    const headers: Record<string, string> = {};
    if (idempotencyKey) {
      headers["X-Idempotency-Key"] = idempotencyKey;
    }
    return this.request<T>(path, {
      method: "PUT",
      body: JSON.stringify(body),
      headers,
    });
  }

}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export const apiClient = new ApiClient(API_BASE_URL);
