import { idempotencyKeys, task } from "@trigger.dev/sdk";
import { python } from "@trigger.dev/python";

import { summarizeTask } from "./summarize-task.js";

type DetectTaskPayload = {
  scan_item_id: string;
  database_url?: string;
};

type DetectTaskOutput = {
  scan_item_id: string;
  outcome: string;
  task_id: string | null;
  observation_id: string;
  processing_state: string;
  error_code: string | null;
};

export const detectTasks = task({
  id: "detect-tasks",
  maxDuration: 120,
  retry: {
    maxAttempts: 3,
    factor: 2,
    minTimeoutInMs: 1_000,
    maxTimeoutInMs: 30_000,
    randomize: true,
  },
  run: async (payload: DetectTaskPayload): Promise<DetectTaskOutput> => {
    const result = await python.runScript("./backend/jobs/detect_tasks.py", [
      JSON.stringify(payload),
    ]);
    const output = JSON.parse(result.stdout.trim()) as DetectTaskOutput;

    if (output.outcome === "task" && output.task_id !== null) {
      const idempotencyKey = await idempotencyKeys.create(
        `summary:${output.task_id}:${output.observation_id}`,
        { scope: "global" },
      );

      await summarizeTask.trigger(
        {
          task_id: output.task_id,
          observation_id: output.observation_id,
          database_url: payload.database_url,
        },
        {
          idempotencyKey,
          concurrencyKey: `task:${output.task_id}`,
        },
      );
    }

    return output;
  },
});
