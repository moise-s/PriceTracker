import { describe, expect, it } from "vitest";
import { type HistoryRow, sortHistoryRows } from "./history-sort";

const rows: HistoryRow[] = [
  { observation_id: "a", observed_at: "2026-09-01T10:00:00Z", store: "Água 2", title: "Banana", price: "9.50", unit_price: "0.09", flagged: false, stale: false, availability: "in_stock", method: "api", review_status: "ok" },
  { observation_id: "b", observed_at: "2026-09-02T10:00:00Z", store: "Água 10", title: "Abacate", price: "100.00", unit_price: "0.10", flagged: true, stale: false, availability: "in_stock", method: "api", review_status: "flagged" },
  { observation_id: "c", observed_at: "2026-09-03T10:00:00Z", store: "Bela", title: "Café", price: null, unit_price: null, flagged: false, stale: true, availability: "in_stock", method: "api", review_status: "ok" },
];
const ids = (key: Parameters<typeof sortHistoryRows>[1], direction: "ascending" | "descending") => sortHistoryRows(rows, key, direction).map((r) => r.observation_id).join("");

describe("all history columns", () => {
  it("sorts dates, titles and store names with locale-aware natural ordering", () => {
    expect(ids("observed_at", "descending")).toBe("cba");
    expect(ids("store", "ascending")).toBe("abc");
    expect(ids("title", "ascending")).toBe("bac");
  });
  it("compares decimal values numerically and keeps missing values last", () => {
    for (const key of ["price", "unit_price"] as const) {
      expect(ids(key, "ascending")).toBe("abc");
      expect(ids(key, "descending")).toBe("bac");
    }
  });
  it("sorts the displayed status, with review taking precedence", () => {
    expect(ids("status", "ascending")).toBe("acb");
    expect(ids("status", "descending")).toBe("bca");
    expect(rows[0]?.observation_id).toBe("a"); // Never mutates query cache data.
  });
});
