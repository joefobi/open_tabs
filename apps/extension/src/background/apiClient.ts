/** HTTP client owned by the service worker. */

import type {
  ApiErrorResponse,
  ClearDataResponse,
  InstallationResponse,
  ManualTaskCreateRequest,
  ManualTaskPatchRequest,
  ScanAcceptedResponse,
  ScanCreateRequest,
  ScanResponse,
  TaskCard,
  TaskListResponse,
} from "./types";

export class ApiClient {
  private readonly baseUrl: string;
  private readonly tokenProvider: () => Promise<string | null>;

  constructor(baseUrl: string, tokenProvider: () => Promise<string | null>) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.tokenProvider = tokenProvider;
  }

  async createInstallation(): Promise<InstallationResponse> {
    return this.request<InstallationResponse>("/v1/installations", {
      method: "POST",
      auth: false,
    });
  }

  async createScan(body: ScanCreateRequest): Promise<ScanAcceptedResponse> {
    return this.request<ScanAcceptedResponse>("/v1/scans", {
      method: "POST",
      auth: true,
      body,
    });
  }

  async getScan(scanId: string): Promise<ScanResponse> {
    return this.request<ScanResponse>(`/v1/scans/${encodeURIComponent(scanId)}`, {
      method: "GET",
      auth: true,
    });
  }

  async listTasks(): Promise<TaskListResponse> {
    return this.request<TaskListResponse>("/v1/tasks", {
      method: "GET",
      auth: true,
    });
  }

  async createManualTask(body: ManualTaskCreateRequest): Promise<TaskCard> {
    return this.request<TaskCard>("/v1/tasks", {
      method: "POST",
      auth: true,
      body,
    });
  }

  async updateManualTask(taskId: string, body: ManualTaskPatchRequest): Promise<TaskCard> {
    return this.request<TaskCard>(`/v1/tasks/${encodeURIComponent(taskId)}`, {
      method: "PATCH",
      auth: true,
      body,
    });
  }

  async deleteTask(taskId: string): Promise<void> {
    await this.request<null>(`/v1/tasks/${encodeURIComponent(taskId)}`, {
      method: "DELETE",
      auth: true,
    });
  }

  async clearData(): Promise<ClearDataResponse> {
    return this.request<ClearDataResponse>("/v1/data", {
      method: "DELETE",
      auth: true,
    });
  }

  private async request<T>(
    path: string,
    options: {
      method: "GET" | "POST" | "PATCH" | "DELETE";
      auth: boolean;
      body?: unknown;
    },
  ): Promise<T> {
    const headers = new Headers({ Accept: "application/json" });

    if (options.body !== undefined) {
      headers.set("Content-Type", "application/json");
    }

    if (options.auth) {
      const token = await this.tokenProvider();
      if (!token) {
        throw new ApiClientError("missing_credentials", "No installation credential is stored.", false);
      }
      headers.set("Authorization", `Bearer ${token}`);
    }

    const response = await fetch(`${this.baseUrl}${path}`, {
      method: options.method,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
    const payload = await this.readJson(response);

    if (!response.ok) {
      const error = this.parseError(payload);
      throw new ApiClientError(error.code, error.message, error.retryable);
    }

    return payload as T;
  }

  private async readJson(response: Response): Promise<unknown> {
    const text = await response.text();
    if (!text) {
      return null;
    }
    return JSON.parse(text) as unknown;
  }

  private parseError(payload: unknown): { code: string; message: string; retryable: boolean } {
    const candidate = payload as Partial<ApiErrorResponse> | null;
    if (candidate?.error?.code && candidate.error.message) {
      return candidate.error;
    }
    return {
      code: "api_error",
      message: "The backend request failed.",
      retryable: true,
    };
  }
}

export class ApiClientError extends Error {
  readonly code: string;
  readonly retryable: boolean;

  constructor(code: string, message: string, retryable: boolean) {
    super(message);
    this.name = "ApiClientError";
    this.code = code;
    this.retryable = retryable;
  }
}
