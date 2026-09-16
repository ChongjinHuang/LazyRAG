import { describe, expect, it } from "vitest";
import { showcaseTechnologyType } from "./classification";

describe("showcaseTechnologyType", () => {
  it("uses the configured technology type when provided", () => {
    expect(showcaseTechnologyType("work", "workflow")).toBe("workflow");
  });

  it("keeps the legacy type-based fallback", () => {
    expect(showcaseTechnologyType("chat")).toBe("skill");
    expect(showcaseTechnologyType("workflow")).toBe("workflow");
  });
});
