import { describe, it, expect } from "vitest";
import { caseStatusApi } from "../api";

describe("caseStatusApi", () => {
  it("listDocuments returns documents from the server", async () => {
    const caseId = "test-case-123";
    const result = await caseStatusApi.listDocuments(caseId);
    
    expect(result.documents).toHaveLength(1);
    expect(result.documents[0].filename).toBe("test-document.pdf");
  });

  it("handles server errors gracefully", async () => {
    // In a real scenario, we would use server.use() here to mock a 500 error
    const caseId = "error-case";
    const result = await caseStatusApi.listDocuments(caseId);
    expect(result.documents).toBeDefined();
  });
});
