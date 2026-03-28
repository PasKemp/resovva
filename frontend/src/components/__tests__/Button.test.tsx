import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { Button } from "../Button";

describe("Button Component", () => {
  it("renders with children", () => {
    render(<Button>Click me</Button>);
    expect(screen.getByText("Click me")).toBeInTheDocument();
  });

  it("calls onClick when clicked", () => {
    const onClickSpy = vi.fn();
    render(<Button onClick={onClickSpy}>Click me</Button>);
    
    fireEvent.click(screen.getByText("Click me"));
    expect(onClickSpy).toHaveBeenCalledTimes(1);
  });

  it("can be disabled", () => {
    const onClickSpy = vi.fn();
    render(<Button disabled onClick={onClickSpy}>Click me</Button>);
    
    const button = screen.getByRole("button");
    expect(button).toBeDisabled();
    
    fireEvent.click(button);
    expect(onClickSpy).not.toHaveBeenCalled();
  });

  it("is disabled when disabled prop is true", () => {
    render(<Button disabled>Disabled</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });
});
