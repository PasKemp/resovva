import { http, HttpResponse } from "msw";

export const handlers = [
  // Mock endpoint for listing documents
  http.get("/api/v1/cases/:caseId/documents", ({ params }) => {
    return HttpResponse.json({
      case_id: params.caseId,
      documents: [
        {
          document_id: "doc-1",
          filename: "test-document.pdf",
          ocr_status: "completed",
          created_at: new Date().toISOString(),
        },
      ],
    });
  }),

  // Add more mocks here as needed
];
