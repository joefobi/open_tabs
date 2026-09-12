import { FormEvent, JSX, useCallback, useEffect, useState } from "react";
import type { SidebarSnapshot, Task, TaskStatus } from "./types";

interface BackendTask {
  id: string;
  origin: "detected" | "manual";
  source_url: string | null;
  title: string;
  status: TaskStatus;
  summary: string | null;
  processing_state: "queued" | "running" | "ready" | "failed";
}

const statusLabel: Record<TaskStatus, string> = {
  action_complete: "Action Complete",
  in_progress: "In Progress",
  needs_attention: "Needs Attention",
  error: "Error",
};

let browserPreview: SidebarSnapshot = {
  tabCount: 7,
  usingFallback: true,
  tasks: [
    { id: "preview-flight", title: "Book flight to Denver", sourceUrl: "https://www.alaskaair.com/booking", status: "needs_attention", summary: "Flight selected for Denver; passenger information is entered, but checkout has not been confirmed.", origin: "detected" },
    { id: "preview-pr", title: "Review PR #142: auth token refresh", sourceUrl: "https://github.com/example/open-tabs/pull/142", status: "in_progress", summary: "Two review comments were addressed. CI checks are still running.", origin: "detected" },
    { id: "preview-research", title: "React Server Components — research", sourceUrl: "https://stackoverflow.com/questions/75973673", status: "action_complete", summary: "Answer found and a useful snippet was copied for the fix.", origin: "detected" },
  ],
};

function normalizeSourceUrl(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const candidate = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
  try {
    const parsed = new URL(candidate);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.href : null;
  } catch {
    return null;
  }
}

function send<T>(message: object): Promise<T> {
  if (typeof chrome === "undefined" || !chrome.runtime?.sendMessage) {
    const action = message as { type: string; title?: string; sourceUrl?: string | null };
    if (action.type === "ADD_MANUAL_TASK" && action.title) browserPreview = { ...browserPreview, tasks: [...browserPreview.tasks, { id: crypto.randomUUID(), title: action.title, sourceUrl: action.sourceUrl ?? null, status: "in_progress", summary: "Added manually — no linked tab yet.", origin: "manual" }] };
    return Promise.resolve(browserPreview as T);
  }
  return chrome.runtime.sendMessage(message).then((reply: { ok: boolean; response?: T; error?: { message?: string } }) => {
    if (!reply.ok) throw new Error(reply.error?.message ?? "The extension request failed.");
    return reply.response as T;
  });
}

async function getSnapshot(): Promise<SidebarSnapshot> {
  if (typeof chrome === "undefined" || !chrome.runtime?.sendMessage) return browserPreview;
  const result = await send<{ tasks: BackendTask[] }>({ type: "LIST_TASKS" });
  const tabs = await chrome.tabs.query({});
  return {
    tabCount: tabs.filter((tab) => tab.url?.startsWith("http")).length,
    usingFallback: false,
    tasks: result.tasks.map((task) => ({
      id: task.id,
      title: task.title,
      sourceUrl: task.source_url,
      status: task.status,
      summary: task.summary ?? "Detecting task…",
      origin: task.origin,
      processingState: task.processing_state,
    })),
  };
}

function RadarIcon(): JSX.Element {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>;
}

function ExternalIcon(): JSX.Element {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 5h5v5M19 5l-9 9"/><path d="M19 14v5H5V5h5"/></svg>;
}

function StatusPill({ status }: { status: TaskStatus }): JSX.Element {
  return <span className={`status status--${status}`}>{statusLabel[status]}</span>;
}

export function Sidebar(): JSX.Element {
  const [snapshot, setSnapshot] = useState<SidebarSnapshot>({ tasks: [], tabCount: 0, usingFallback: true });
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [isAdding, setIsAdding] = useState(false);
  const [title, setTitle] = useState("");
  const [url, setUrl] = useState("");
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try { setSnapshot(await getSnapshot()); }
    catch {
      setSnapshot({ ...browserPreview, tasks: [...browserPreview.tasks] });
      setNotice("Showing reliable demo tasks while the API reconnects.");
    }
  }, []);

  useEffect(() => { void refresh(); const timer = window.setInterval(() => void refresh(), 2000); return () => window.clearInterval(timer); }, [refresh]);

  const addTask = async (event: FormEvent) => {
    event.preventDefault();
    if (!title.trim()) return;
    const sourceUrl = normalizeSourceUrl(url);
    if (url.trim() && !sourceUrl) { setNotice("Enter a valid http(s) source URL."); return; }
    await send({ type: "ADD_MANUAL_TASK", clientRequestId: crypto.randomUUID(), title: title.trim(), sourceUrl });
    await refresh(); setTitle(""); setUrl(""); setIsAdding(false);
  };

  const openTask = async (task: Task) => {
    await send({ type: "OPEN_TASK_SOURCE", url: task.sourceUrl });
    setNotice("Jumped to the source tab.");
  };

  return <main className="sidebar-shell">
    <header className="sidebar-header">
      <RadarIcon />
      <div className="brand"><h1>OpenTabs AI</h1><p>{snapshot.tabCount} tabs scanned · {snapshot.tasks.length} tasks</p></div>
      <button className="btn btn-primary btn-icon" aria-label="Add task" onClick={() => setIsAdding((value) => !value)}>+</button>
    </header>

    {isAdding && <form className="card elev-sm manual-form" onSubmit={addTask}>
      <label className="field">Task title<input className="input" required value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Renew domain" /></label>
      <label className="field">Source URL <span>(optional)</span><input className="input" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="e.g. namecheap.com" /></label>
      <div className="form-actions"><button className="btn btn-primary" type="submit">Add task</button><button className="btn btn-ghost" type="button" onClick={() => setIsAdding(false)}>Cancel</button></div>
    </form>}

    {notice && <button className="notice" onClick={() => setNotice(null)}>{notice}</button>}
    <section className="task-list" aria-label="Detected tasks">
      {snapshot.tasks.map((task) => <article className={`card elev-sm task-card ${task.origin === "manual" ? "task-card--manual" : ""}`} key={task.id}>
        <div className="task-top"><div><h2 className={task.status === "action_complete" ? "complete" : ""}>{task.title}</h2><p className="source-label">{task.origin === "manual" ? "Manually added" : new URL(task.sourceUrl ?? "https://opentabs.local").hostname}</p></div>
          {task.sourceUrl && <button className="btn btn-ghost btn-icon jump" aria-label={`Jump to ${task.title}`} onClick={() => void openTask(task)}><ExternalIcon /></button>}
        </div>
        <div className="status-row"><StatusPill status={task.status} /><button className="btn btn-ghost summary-toggle" onClick={() => setExpanded((items) => ({ ...items, [task.id]: !items[task.id] }))}>{expanded[task.id] ? "Hide summary ˄" : "Show summary ˅"}</button></div>
        {expanded[task.id] && <p className="card-body summary">{task.summary}</p>}
      </article>)}
    </section>
  </main>;
}
