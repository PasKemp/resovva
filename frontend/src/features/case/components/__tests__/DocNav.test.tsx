import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { DocNav } from "../DocNav";
import type { DocumentListItem } from "../../../../services/api";

const mockDocs: DocumentListItem[] = [
  { document_id: "doc-1", filename: "test-1.pdf", ocr_status: "completed", created_at: "2023-01-01", document_type: "invoice" },
  { document_id: "doc-2", filename: "test-2.pdf", ocr_status: "pending", created_at: "2023-01-02", document_type: "contract" },
];

describe("DocNav Component", () => {
  it("renders the document list", () => {
    render(<DocNav docs={mockDocs} selectedId="doc-1" onSelect={() => {}} open={true} onToggle={() => {}} />);
    
    expect(screen.getByText("test-1.pdf")).toBeInTheDocument();
    expect(screen.getByText("test-2.pdf")).toBeInTheDocument();
  });

  it("calls onSelect when a document is clicked", () => {
    const onSelectSpy = vi.fn();
    render(<DocNav docs={mockDocs} selectedId="doc-1" onSelect={onSelectSpy} open={true} onToggle={() => {}} />);
    
    fireEvent.click(screen.getByText("test-2.pdf"));
    expect(onSelectSpy).toHaveBeenCalledWith("doc-2");
  });

  it("calls onToggle when the toggle button is clicked", () => {
    const onToggleSpy = vi.fn();
    render(<DocNav docs={mockDocs} selectedId="doc-1" onSelect={() => {}} open={true} onToggle={onToggleSpy} />);
    
    // Toggle button is the one with the title
    const toggleBtn = screen.getByTitle(/Seitenleiste/);
    fireEvent.click(toggleBtn);
    expect(onToggleSpy).toHaveBeenCalledTimes(1);
  });

  it("shows 'Verarbeitung' for pending documents", () => {
    render(<DocNav docs={mockDocs} selectedId="doc-1" onSelect={() => {}} open={true} onToggle={() => {}} />);
    // Use a regex to be more flexible
    expect(screen.getByText(/Verarbeitung/)).toBeInTheDocument();
  });
});
