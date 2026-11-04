import { afterEach, expect, test, vi } from "vitest";
import { api, ApiError } from "./api";
afterEach(() => vi.unstubAllGlobals());
test("writes send the reviewed version and same-origin credentials", async () => {
  const fetcher = vi.fn().mockResolvedValue({
    ok: true,
    status: 201,
    json: async () => ({ id: "new" }),
  });
  vi.stubGlobal("fetch", fetcher);
  await api("/rules", "POST", { title: "Rule" }, 12);
  expect(fetcher).toHaveBeenCalledWith(
    "/api/rules",
    expect.objectContaining({
      credentials: "same-origin",
      headers: expect.objectContaining({
        "If-Match": '"12"',
        "X-Jadwai-Request": "1",
      }),
    }),
  );
});
test("stale changes are errors, never reported as successful saves", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({ detail: "stale_edit" }),
    }),
  );
  await expect(api("/rules", "POST", {}, 1)).rejects.toMatchObject({
    code: "stale_edit",
    status: 409,
  });
});
test("network errors have a stable localizable code", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
  await expect(api("/workspace")).rejects.toEqual(
    new ApiError("connection_failed", 0),
  );
});
test("delete responses need no JSON body", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 204 }));
  expect(
    await api("/records/rooms/123", "DELETE", undefined, 1),
  ).toBeUndefined();
});
