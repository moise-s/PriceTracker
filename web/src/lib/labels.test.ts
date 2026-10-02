import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { RUN_STATUS, TARGET_STATUS } from "./labels";

// Contract drift guard: every status the API can return has a Portuguese label, icon and help.
const spec = JSON.parse(readFileSync(path.resolve(process.cwd(), "openapi.json"), "utf-8"));
const enumOf = (name: string): string[] => spec.components.schemas[name].enum;

describe("status labels", () => {
  it("cover every target status the API can report", () => {
    for (const status of enumOf("TargetStatus")) {
      expect(TARGET_STATUS[status], status).toBeDefined();
      expect(TARGET_STATUS[status]!.help.length, status).toBeGreaterThan(10);
    }
  });
  it("cover every run status", () => {
    for (const status of enumOf("RunStatus")) expect(RUN_STATUS[status], status).toBeDefined();
  });
  it("never reuse one label for two different failure modes", () => {
    const labels = Object.values(TARGET_STATUS).map((s) => s.label);
    expect(new Set(labels).size).toBe(labels.length);
  });
});
