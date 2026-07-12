// Route a log/status line into the planner, executor, or system stream.
//
// The backend emits a single flat log stream; these heuristics (ported from
// the original UI) split planner vs executor chatter so developers can filter.

import type { LogSource } from "./types";

const PLANNER_PATTERNS: RegExp[] = [
  /planning tests for:/i,
  /plan for .*test cases/i,
  /primary planner failed/i,
  /all planners failed/i,
  /planner needs input/i,
  /generated test cases/i,
  /gemini planner/i,
  /planner clarification/i,
];

const EXECUTOR_PATTERNS: RegExp[] = [
  /executing \d+ test cases/i,
  /starting executor:/i,
  /executor failed/i,
  /executor crashed/i,
  /executor task/i,
  /test plan has no test cases/i,
  /no test plan found/i,
  /executor \d+\//i,
];

export function classifySource(type: string, content: string): LogSource {
  if (type === "interrupt") return "planner";

  const text = String(content ?? "");
  if (PLANNER_PATTERNS.some((rx) => rx.test(text))) return "planner";
  if (EXECUTOR_PATTERNS.some((rx) => rx.test(text))) return "executor";
  return "system";
}
