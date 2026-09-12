import type { SidebarSnapshot, Task, TaskStatus } from "../sidebar/types";

const API_BASE = "http://localhost:8000";

const fallbackTasks: Task[] = [
  { id: "seed-flight", title: "Book flight to Denver", sourceUrl: "https://www.alaskaair.com/booking", status: "needs_attention", summary: "Flight selected for Denver; passenger information is entered, but checkout has not been confirmed.", origin: "detected", processingState: "ready" },
  { id: "seed-pr", title: "Review PR #142: auth token refresh", sourceUrl: "https://github.com/example/open-tabs/pull/142", status: "in_progress", summary: "Two review comments were addressed. CI checks are still running.", origin: "detected", processingState: "ready" },
  { id: "seed-research", title: "React Server Components — research", sourceUrl: "https://stackoverflow.com/questions/75973673", status: "action_complete", summary: "Answer found and a useful snippet was copied for the fix.", origin: "detected", processingState: "ready" },
];

async function getLocalTasks(): Promise<Task[]> {
  const stored = await chrome.storage.local.get("tasks");
  if (!stored.tasks) await chrome.storage.local.set({ tasks: fallbackTasks });
  return (stored.tasks ?? fallbackTasks) as Task[];
}

async function snapshot(): Promise<SidebarSnapshot> {
  const tabs = await chrome.tabs.query({});
  const tasks = await getLocalTasks();
  const detected = tabs.map(detectTab).filter((task): task is Task => task !== null);
  const merged = [...tasks];
  for (const task of detected) if (!merged.some((existing) => existing.sourceUrl === task.sourceUrl)) merged.push(task);
  if (merged.length !== tasks.length) await chrome.storage.local.set({ tasks: merged });
  return { tasks: merged, tabCount: tabs.filter((tab) => !!tab.url && !tab.url.startsWith("chrome:")).length, usingFallback: true };
}

/** Derive a bounded demo task from the PRD's URL-first supported signals. */
function detectTab(tab: chrome.tabs.Tab): Task | null {
  const url = tab.url;
  if (!url || !/^https?:/.test(url)) return null;
  const source = new URL(url);
  const title = tab.title?.trim() || source.hostname;
  let task: Omit<Task, "id" | "sourceUrl"> | null = null;
  if (source.hostname === "github.com" && /\/pull\/\d+/.test(source.pathname)) task = { title: `Review ${title}`, status: "in_progress", summary: "Pull request is open. Review progress will update when the background summary is ready.", origin: "detected", processingState: "running" };
  else if (source.hostname === "github.com" && /\/issues\/\d+/.test(source.pathname)) task = { title: `Check bug: ${title}`, status: "in_progress", summary: "Issue is open and ready for review.", origin: "detected", processingState: "running" };
  else if (/stackoverflow\.com$|developer\.mozilla\.org$|docs\./.test(source.hostname)) task = { title: `Research: ${title}`, status: "in_progress", summary: "Research page detected; synthesizing where you left off.", origin: "detected", processingState: "running" };
  else if (source.hostname === "mail.google.com") task = { title: `Reply to email: ${title}`, status: "needs_attention", summary: "Email workflow detected. A reply may need your attention.", origin: "detected", processingState: "running" };
  else if (/alaskaair\.com$|united\.com$|delta\.com$/.test(source.hostname) || /\/cart\b/.test(source.pathname)) task = { title: `Finish: ${title}`, status: "needs_attention", summary: "Checkout flow detected. Confirm the next step when you are ready.", origin: "detected", processingState: "running" };
  return task ? { ...task, id: `tab-${tab.id ?? crypto.randomUUID()}`, sourceUrl: url } : null;
}

async function persist(tasks: Task[]): Promise<SidebarSnapshot> {
  await chrome.storage.local.set({ tasks });
  return snapshot();
}

async function addManual(title: string, sourceUrl: string | null): Promise<SidebarSnapshot> {
  const tasks = await getLocalTasks();
  const task: Task = { id: crypto.randomUUID(), title, sourceUrl, status: "in_progress", summary: "Added manually — no linked tab yet.", origin: "manual", processingState: "ready" };
  // The local write is deliberate: it keeps the sidebar usable while the current backend
  // does not yet expose the extension's anonymous credential/bootstrap flow to this build.
  return persist([...tasks, task]);
}

async function updateTask(id: string, status: TaskStatus): Promise<SidebarSnapshot> {
  const tasks = await getLocalTasks();
  return persist(tasks.map((task) => task.id === id ? { ...task, status, summary: status === "action_complete" ? "Confirmed just now." : status === "in_progress" ? "Paused — you dismissed the prompt." : task.summary } : task));
}

async function openSource(sourceUrl: string | null): Promise<void> {
  if (!sourceUrl) return;
  const tabs = await chrome.tabs.query({});
  const existing = tabs.find((tab) => tab.url === sourceUrl || tab.url?.startsWith(sourceUrl));
  if (existing?.id) { await chrome.tabs.update(existing.id, { active: true }); if (existing.windowId) await chrome.windows.update(existing.windowId, { focused: true }); return; }
  await chrome.tabs.create({ url: sourceUrl });
}

chrome.runtime.onInstalled.addListener(() => { chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }); });

chrome.runtime.onMessage.addListener((message: { type: string; id?: string; title?: string; sourceUrl?: string | null; status?: TaskStatus }) => {
  if (message.type === "LIST_TASKS") return snapshot();
  if (message.type === "ADD_MANUAL_TASK" && message.title) return addManual(message.title, message.sourceUrl ?? null);
  if (message.type === "UPDATE_TASK" && message.id && message.status) return updateTask(message.id, message.status);
  if (message.type === "OPEN_TASK_SOURCE") return openSource(message.sourceUrl ?? null);
  return { apiBase: API_BASE };
});
