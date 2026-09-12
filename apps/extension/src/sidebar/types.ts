export type TaskStatus = "action_complete" | "in_progress" | "needs_attention" | "error";

export interface Task {
  id: string;
  title: string;
  sourceUrl: string | null;
  status: TaskStatus;
  summary: string;
  origin: "detected" | "manual";
  processingState?: "queued" | "running" | "ready" | "failed";
}

export interface SidebarSnapshot {
  tasks: Task[];
  tabCount: number;
  usingFallback: boolean;
}
