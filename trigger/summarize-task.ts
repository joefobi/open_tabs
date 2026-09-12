import { task } from "@trigger.dev/sdk";
import { python } from "@trigger.dev/python";

type SummarizeTaskPayload = {
  task_id: string;
  observation_id: string;
  database_url?: string;
};

type SummarizeTaskOutput = {
  task_id: string;
  observation_id: string;
  processing_state: string;
  error_code: string | null;
};

export const summarizeTask = task({
  id: "summarize-task",
  maxDuration: 120,
  retry: {
    maxAttempts: 3,
    factor: 2,
    minTimeoutInMs: 1_000,
    maxTimeoutInMs: 30_000,
    randomize: true,
  },
  run: async (payload: SummarizeTaskPayload): Promise<SummarizeTaskOutput> => {
    const result = await python.runScript("./backend/jobs/summarize_task.py", [
      JSON.stringify(payload),
    ]);
    return JSON.parse(result.stdout.trim()) as SummarizeTaskOutput;
  },
});
