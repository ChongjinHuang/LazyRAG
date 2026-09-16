import { describe, expect, it } from "vitest";
import { showcaseTechnologyType } from "./classification";

describe("showcaseTechnologyType", () => {
  it("uses the capability type without case-specific overrides", () => {
    expect(showcaseTechnologyType("chat")).toBe("skill");
    expect(showcaseTechnologyType("work")).toBe("skill");
    expect(showcaseTechnologyType("workflow")).toBe("workflow");
  });
});
