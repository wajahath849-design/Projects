import { describe, expect, it } from "vitest";
import { csvHeaders, csvValues } from "./csv";

describe("CSV headers", () => {
  it("reads quoted column names and BOMs", () => {
    expect(csvHeaders('\uFEFFdate,"product, category","a""b"\r\n2026-01-01,x,y')).toEqual(["date", "product, category", 'a"b']);
  });
  it("rejects ambiguous and malformed headers", () => {
    for (const text of ["", "date,date\n", "date,,sales\n", 'date,"unclosed']) expect(() => csvHeaders(text)).toThrow();
  });
  it("collects exact values including missing cells", () => {
    expect(csvValues("region,category\r\nBerlin,Clothing\r\nHamburg,\r\nBerlin,Footwear")).toEqual({
      region: ["Berlin", "Hamburg"], category: ["Clothing", "Footwear", null],
    });
  });
});
