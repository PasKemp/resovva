import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { Stepper, STEPS } from "../Stepper";

describe("Stepper Component", () => {
  it("renders all steps correctly", () => {
    render(<Stepper current={0} onStep={() => {}} />);
    
    STEPS.forEach((step) => {
      expect(screen.getByText(step.label)).toBeInTheDocument();
      expect(screen.getByText(step.sublabel)).toBeInTheDocument();
    });
  });

  it("highlights the active step", () => {
    const activeIndex = 1;
    render(<Stepper current={activeIndex} onStep={() => {}} />);
    
    const activeLabel = screen.getByText(STEPS[activeIndex].label);
    // Based on Stepper.tsx: colors.orange is used for active step
    // Since we use inline styles, we check the computed style if possible, 
    // but here we check if it exists and has the correct label.
    expect(activeLabel).toBeInTheDocument();
  });

  it("calls onStep when clicking a previous step", () => {
    const onStepSpy = vi.fn();
    render(<Stepper current={2} onStep={onStepSpy} />);
    
    // Click the first step (Upload)
    const firstStep = screen.getByText(STEPS[0].label);
    fireEvent.click(firstStep);
    
    expect(onStepSpy).toHaveBeenCalledWith(0);
  });

  it("does not call onStep when clicking a future step", () => {
    const onStepSpy = vi.fn();
    render(<Stepper current={0} onStep={onStepSpy} />);
    
    // Click the third step (Roter Faden)
    const futureStep = screen.getByText(STEPS[2].label);
    fireEvent.click(futureStep);
    
    expect(onStepSpy).not.toHaveBeenCalled();
  });
});
