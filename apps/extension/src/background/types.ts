/** Shared types for the extension middle layer. */

export type ExtractionState = "ready" | "inaccessible" | "unloaded" | "error";

export type ProcessingState =
  | "queued"
  | "running"
  | "ready"
  | "failed"
  | "unchanged"
  | "superseded";

export interface InstallationCredential {
  ownerId: string;
  installationToken: string;
  createdAt: string;
}

export interface InstallationResponse {
  owner_id: string;
  installation_credential: string;
  token_type: "bearer";
}

export interface ObservationPayload {
  client_observation_id: string;
  source_url: string;
  title: string;
  observed_at: string;
  text: string;
  extraction_state: ExtractionState;
  truncated: boolean;
  screenshot_id?: string;
}

export interface ScanCreateRequest {
  client_request_id: string;
  observations: ObservationPayload[];
}

export interface ScanAcceptedResponse {
  scan_id: string;
  state: ProcessingState;
}

export interface ScanCounts {
  total: number;
  accepted: number;
  unchanged: number;
  superseded: number;
  failed: number;
}

export interface ScanItemResponse {
  observation_id: string;
  task_id: string | null;
  source_key: string;
  processing_state: ProcessingState;
  detection_outcome: string | null;
  error_code: string | null;
}

export interface ScanResponse {
  scan_id: string;
  client_request_id: string;
  state: ProcessingState;
  counts: ScanCounts;
  items: ScanItemResponse[];
  error_code: string | null;
  created_at: string;
  updated_at: string;
}

export type TaskOrigin = "detected" | "manual";
export type TaskType = "github" | "research" | "email" | "travel" | "shopping" | "manual";
export type TaskStatus = "in_progress" | "needs_attention" | "action_complete" | "error";
export type TaskProcessingState = "queued" | "running" | "ready" | "failed";

export interface TaskCard {
  id: string;
  origin: TaskOrigin;
  source_key: string | null;
  source_url: string | null;
  type: TaskType;
  title: string;
  status: TaskStatus;
  status_reason: string | null;
  summary: string | null;
  processing_state: TaskProcessingState;
  processing_error_code: string | null;
  observed_at: string | null;
  updated_at: string;
}

export interface TaskListResponse {
  tasks: TaskCard[];
}

export interface ManualTaskCreateRequest {
  client_request_id: string;
  title: string;
}

export interface ManualTaskPatchRequest {
  title?: string | null;
  status?: TaskStatus | null;
  status_reason?: string | null;
}

export interface ClearDataResponse {
  deleted_tasks: number;
}

export interface ApiErrorDetail {
  code: string;
  message: string;
  retryable: boolean;
}

export interface ApiErrorResponse {
  error: ApiErrorDetail;
}

export interface CollectedPage {
  tabId: number;
  url: string;
  title: string;
  observedAt: string;
  text: string;
  extractionState: ExtractionState;
  truncated: boolean;
  contentHash: string;
  errorCode?: string;
}

export interface PendingScan {
  clientRequestId: string;
  body: ScanCreateRequest;
  createdAt: string;
  lastAttemptAt?: string;
  scanId?: string;
  state: "pending" | "submitted";
}

export interface ChromeTab {
  id?: number;
  url?: string;
  title?: string;
  status?: string;
  incognito?: boolean;
}

export interface ChromeStorageArea {
  get(keys: string | string[] | Record<string, unknown> | null, callback: (items: Record<string, unknown>) => void): void;
  set(items: Record<string, unknown>, callback?: () => void): void;
  remove(keys: string | string[], callback?: () => void): void;
}

export interface ChromeEvent<TCallback> {
  addListener(callback: TCallback): void;
}

export interface ChromeApi {
  alarms?: {
    create(
      name: string,
      alarmInfo: { delayInMinutes?: number; periodInMinutes?: number },
    ): void;
    onAlarm: ChromeEvent<(alarm: { name: string }) => void>;
  };
  runtime: {
    onInstalled?: ChromeEvent<() => void>;
    onMessage: {
      addListener(
        callback: (
          message: ExtensionMessage,
          sender: unknown,
          sendResponse: (response?: unknown) => void,
        ) => boolean | void,
      ): void;
    };
    onStartup?: ChromeEvent<() => void>;
  };
  scripting: {
    executeScript<T>(details: {
      target: { tabId: number };
      func: () => T;
    }): Promise<Array<{ result?: T }>>;
  };
  storage: {
    local: ChromeStorageArea;
  };
  tabs: {
    create(createProperties: Record<string, unknown>): Promise<ChromeTab>;
    get(tabId: number): Promise<ChromeTab>;
    onActivated?: ChromeEvent<
      (activeInfo: { tabId: number; windowId: number }) => void
    >;
    onUpdated?: ChromeEvent<
      (
        tabId: number,
        changeInfo: { status?: string; url?: string },
        tab: ChromeTab,
      ) => void
    >;
    query(queryInfo: Record<string, unknown>): Promise<ChromeTab[]>;
    update(tabId: number, updateProperties: Record<string, unknown>): Promise<ChromeTab>;
  };
  windows: {
    update(windowId: number, updateInfo: Record<string, unknown>): Promise<unknown>;
  };
}

export type ExtensionMessage =
  | { type: "GET_SCAN"; scanId: string }
  | { type: "LIST_TASKS" }
  | { type: "ADD_MANUAL_TASK"; clientRequestId: string; title: string }
  | { type: "UPDATE_MANUAL_TASK"; taskId: string; patch: ManualTaskPatchRequest }
  | { type: "DELETE_TASK"; taskId: string }
  | { type: "CLEAR_DATA" }
  | { type: "OPEN_TASK_SOURCE"; tabId?: number; url: string };
