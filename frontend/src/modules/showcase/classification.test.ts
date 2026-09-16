import { describe, expect, it } from "vitest";
import {
  STEP_EXECUTION_SKILL_CASE_IDS,
  showcaseTechnologyType,
} from "./classification";

describe("showcaseTechnologyType", () => {
  it("classifies agent team orchestration as step execution", () => {
    expect(STEP_EXECUTION_SKILL_CASE_IDS).toContain("agent-team-orchestration");
    expect(showcaseTechnologyType("work", "agent-team-orchestration")).toBe("workflow");
  });

  it("keeps workflow capabilities in step execution without changing other skills", () => {
    expect(showcaseTechnologyType("chat")).toBe("skill");
    expect(showcaseTechnologyType("work", "devops")).toBe("skill");
    expect(showcaseTechnologyType("workflow")).toBe("workflow");
  });
});
