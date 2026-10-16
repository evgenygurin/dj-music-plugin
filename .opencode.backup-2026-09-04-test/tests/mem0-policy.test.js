import { test, expect, describe } from "bun:test";
import { classifyDurableMemory, redactMemoryText, buildProjectFilters } from "../mem0-policy.js";

describe("Mem0 policy", () => {
  test("classifies durable architecture decisions", () => {
    expect(classifyDurableMemory("Решили использовать Mem0 Platform как единый backend памяти проекта.")).toBe("architecture_decisions");
  });

  test("redacts credential-shaped values before storage", () => {
    const input = "Use key m0-ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890 in local configuration.";
    expect(redactMemoryText(input)).not.toContain("m0-ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890");
    expect(redactMemoryText(input)).toContain("[REDACTED]");
  });

  test("builds project-scoped filters", () => {
    expect(buildProjectFilters("user-1", "project-1")).toEqual({
      AND: [{ user_id: "user-1" }, { app_id: "project-1" }]
    });
  });
});


test("performs proactive read-only retrieval when project has zero memories", async () => {
  const calls = [];
  const mem0 = {
    search: async (...args) => { calls.push(args); return { results: [] }; },
    add: async () => { throw new Error("capture not awaited in retrieval test"); },
  };
  const { chatMessage } = (await import("../mem0-policy.js")).createMem0PolicyHooks({
    mem0, userId: "user-1", appId: "project-1", sessionId: "session-1", branch: "main"
  });
  const output = { parts: [{ type: "text", text: "Проверяем архитектурное решение проекта и текущую конфигурацию Mem0 для дальнейшей работы." }] };
  await chatMessage({ parts: output.parts }, output);
  expect(calls).toHaveLength(2);
  expect(calls[0][1].filters).toEqual({ AND: [{ user_id: "user-1" }, { app_id: "project-1" }] });
  expect(calls[1][1].filters).toEqual({ AND: [{ user_id: "user-1" }, { app_id: "project-1" }, { metadata: { type: "architecture_decisions" } }] });
});
