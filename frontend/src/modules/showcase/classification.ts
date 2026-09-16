export type ShowcaseEntryType = "chat" | "work";
export type ShowcaseTechnologyType = "skill" | "workflow";

export const SHOWCASE_ENTRY_QUERY_PARAM = "showcase_entry";

export const STEP_EXECUTION_SKILL_CASE_IDS = new Set([
  "agent-team-orchestration",
]);

export function showcaseEntryType(capabilityType: string): ShowcaseEntryType {
  return capabilityType === "chat" ? "chat" : "work";
}

export function showcaseTechnologyType(
  capabilityType: string,
  caseId?: string,
): ShowcaseTechnologyType {
  const isStepExecution =
    capabilityType === "workflow" ||
    (caseId !== undefined && STEP_EXECUTION_SKILL_CASE_IDS.has(caseId));
  return isStepExecution ? "workflow" : "skill";
}

export function parseShowcaseEntryType(value: string | null): ShowcaseEntryType | null {
  return value === "chat" || value === "work" ? value : null;
}

export function buildShowcaseLaunchPath(
  caseId: string,
  capabilityType: string,
  taskId?: string,
) {
  const params = buildShowcaseLaunchParams(caseId, capabilityType, taskId);
  return `/agent/chat/home?${params.toString()}`;
}

export function buildShowcaseLaunchParams(
  caseId: string,
  capabilityType: string,
  taskId?: string,
) {
  const params = new URLSearchParams({ showcase_case: caseId });
  if (taskId) {
    params.set("showcase_task", taskId);
  }
  params.set(SHOWCASE_ENTRY_QUERY_PARAM, showcaseEntryType(capabilityType));
  return params;
}

export function matchesShowcaseEntryType(
  capabilityType: string,
  entryType: ShowcaseEntryType,
) {
  return showcaseEntryType(capabilityType) === entryType;
}
