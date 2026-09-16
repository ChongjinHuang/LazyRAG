import { describe, expect, it } from "vitest";
import { showcaseTechnologyType } from "./classification";

describe("showcaseTechnologyType", () => {
  it("classifies agent team orchestration as step execution", () => {
    expect(showcaseTechnologyType("work", "agent-team-orchestration")).toBe("workflow");
  });

  it("keeps the legacy type-based fallback", () => {
    expect(showcaseTechnologyType("chat")).toBe("skill");
    expect(showcaseTechnologyType("workflow")).toBe("workflow");
  });
});
