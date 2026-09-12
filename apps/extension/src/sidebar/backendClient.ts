import type { SidebarSnapshot, Task, TaskStatus } from "./types";

interface InstallationResponse {
  owner_id: string;
  installation_credential: string;
  token_type: "bearer";
}

interface BackendTask {
  id: string;
  origin: "detected" | "manual";
  source_url: string | null;
  title: string;
  status: TaskStatus;
  summary: string | null;
  processing_state: "queued" | "running" | "ready" | "failed";
}

interface TaskListResponse {
  tasks: BackendTask[];
}

interface ExtensionReply<T> {
  ok: boolean;
  response?: T;
  error?: { message?: string };
}

const API_BASE_URL = import.meta.env.VITE_OPEN_TABS_API_BASE_URL ?? "http://localhost:8000";
const CREDENTIAL_KEY = "openTabs.installationCredential";

export async function listSidebarSnapshot(): Promise<SidebarSnapshot> {
  const result = await send<TaskListResponse>({ type: "LIST_TASKS" });
  return {
    tabCount: await countHttpTabs(),
    usingFallback: false,
    tasks: result.tasks.map(toTask),
  };
}

export async function addManualTask(title: string, sourceUrl: string | null): Promise<void> {
  await send({
    type: "ADD_MANUAL_TASK",
    clientRequestId: crypto.randomUUID(),
    title,
    sourceUrl,
  });
}

export async function openTaskSource(task: Task): Promise<boolean> {
  if (!task.sourceUrl) {
    return false;
  }
  const result = await send<{ opened: boolean }>({
    type: "OPEN_TASK_SOURCE",
    url: task.sourceUrl,
  });
  return result.opened;
}

async function send<T>(message: Record<string, unknown>): Promise<T> {
  if (hasExtensionRuntime()) {
    const reply = await chrome.runtime.sendMessage(message) as ExtensionReply<T>;
    if (!reply.ok) {
      throw new Error(reply.error?.message ?? "The extension request failed.");
    }
    return reply.response as T;
  }

  return sendToBackend<T>(message);
}

function hasExtensionRuntime(): boolean {
  return typeof chrome !== "undefined" && Boolean(chrome.runtime?.sendMessage);
}

async function sendToBackend<T>(message: Record<string, unknown>): Promise<T> {
  switch (message.type) {
    case "LIST_TASKS":
      return request<T>("/v1/tasks");
    case "ADD_MANUAL_TASK":
      return request<T>("/v1/tasks", {
        method: "POST",
        body: {
          client_request_id: message.clientRequestId,
          title: message.title,
          source_url: message.sourceUrl,
        },
      });
    case "OPEN_TASK_SOURCE":
      window.open(String(message.url), "_blank", "noopener,noreferrer");
      return Promise.resolve({ opened: true } as T);
    default:
      throw new Error("Unsupported browser request.");
  }
}

async function request<T>(
  path: string,
  options: { method?: "GET" | "POST"; body?: Record<string, unknown> } = {},
): Promise<T> {
  const credential = await ensureCredential();
  const headers = new Headers({
    Accept: "application/json",
    Authorization: `Bearer ${credential.installation_credential}`,
  });
  if (options.body) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) as unknown : null;
  if (!response.ok) {
    throw new Error(errorMessage(payload));
  }
  return payload as T;
}

async function ensureCredential(): Promise<InstallationResponse> {
  const stored = window.localStorage.getItem(CREDENTIAL_KEY);
  if (stored) {
    return JSON.parse(stored) as InstallationResponse;
  }

  const response = await fetch(`${API_BASE_URL}/v1/installations`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  const credential = await response.json() as InstallationResponse;
  if (!response.ok) {
    throw new Error("Could not create an anonymous backend installation.");
  }
  window.localStorage.setItem(CREDENTIAL_KEY, JSON.stringify(credential));
  return credential;
}

async function countHttpTabs(): Promise<number> {
  if (!hasExtensionRuntime()) {
    return 0;
  }
  const tabs = await chrome.tabs.query({});
  return tabs.filter((tab) => tab.url?.startsWith("http")).length;
}

function toTask(task: BackendTask): Task {
  return {
    id: task.id,
    title: task.title,
    sourceUrl: task.source_url,
    status: task.status,
    summary: task.summary ?? "Detecting task...",
    origin: task.origin,
    processingState: task.processing_state,
  };
}

function errorMessage(payload: unknown): string {
  const candidate = payload as { error?: { message?: string } } | null;
  return candidate?.error?.message ?? "Backend request failed.";
}
