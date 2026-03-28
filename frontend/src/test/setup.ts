import "@testing-library/jest-dom";
import { beforeAll, afterEach, afterAll } from "vitest";
import { server } from "./mocks/server";

// Set a base URL for API calls in tests to avoid relative URL errors in Node environment
const BASE_URL = "http://localhost";
(globalThis as any).import = {
  meta: {
    env: {
      VITE_API_URL: BASE_URL,
    },
  },
};

// Start MSW server before all tests
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));

// Reset handlers after each test (essential for test isolation)
afterEach(() => server.resetHandlers());

// Close server after all tests
afterAll(() => server.close());
