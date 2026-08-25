import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiFetch, isMockMode } from "./client";

describe("isMockMode", () => {
  beforeEach(() => {
    delete process.env.NEXT_PUBLIC_USE_MOCK;
  });

  it("defaults to true when env is unset (local dev has no backend)", () => {
    expect(isMockMode()).toBe(true);
  });

  it("returns true when set to 'true'", () => {
    process.env.NEXT_PUBLIC_USE_MOCK = "true";
    expect(isMockMode()).toBe(true);
  });

  it("returns false when set to 'false'", () => {
    process.env.NEXT_PUBLIC_USE_MOCK = "false";
    expect(isMockMode()).toBe(false);
  });

  it("returns false when set to '0'", () => {
    process.env.NEXT_PUBLIC_USE_MOCK = "0";
    expect(isMockMode()).toBe(false);
  });
});

describe("apiFetch", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    process.env.NEXT_PUBLIC_USE_MOCK = "false";
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://test.local/api/v1";
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns parsed JSON on 2xx", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ ok: true, value: 42 }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const result = await apiFetch<{ ok: boolean; value: number }>("/jobs/1");
    expect(result).toEqual({ ok: true, value: 42 });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://test.local/api/v1/jobs/1",
      expect.objectContaining({ headers: expect.any(Object) }),
    );
  });

  it("throws ApiError with status on non-2xx", async () => {
    fetchMock.mockResolvedValue(new Response("not found", { status: 404 }));

    await expect(apiFetch("/jobs/1")).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
    });
  });

  it("truncates error body to 200 chars", async () => {
    const big = "x".repeat(500);
    fetchMock.mockResolvedValue(new Response(big, { status: 500 }));

    await expect(apiFetch("/jobs/1")).rejects.toThrow(
      /x{200}x{0}/, // first 200 chars of x
    );
  });

  it("throws ApiError on timeout (AbortError)", async () => {
    fetchMock.mockImplementation(
      () =>
        new Promise((_, reject) => {
          const err = new Error("aborted");
          err.name = "AbortError";
          reject(err);
        }),
    );

    await expect(
      apiFetch("/jobs/1", { timeoutMs: 50 }),
    ).rejects.toMatchObject({
      name: "ApiError",
      message: expect.stringMatching(/timed out/),
    });
  });

  it("refuses to run in mock mode", async () => {
    process.env.NEXT_PUBLIC_USE_MOCK = "true";

    await expect(apiFetch("/jobs/1")).rejects.toThrow(/Mock mode/);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("throws when API base URL is missing", async () => {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;

    await expect(apiFetch("/jobs/1")).rejects.toThrow(
      /NEXT_PUBLIC_API_BASE_URL/,
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("serializes JSON body on POST with Content-Type header", async () => {
    fetchMock.mockResolvedValue(
      new Response('{"versionId":"x"}', { status: 200 }),
    );

    await apiFetch("/jobs/x/publish", {
      method: "POST",
      body: { jobId: "x", version: "v2" },
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://test.local/api/v1/jobs/x/publish",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          Accept: "application/json",
        }),
        body: JSON.stringify({ jobId: "x", version: "v2" }),
      }),
    );
  });

  it("POST without body still sends Content-Type header", async () => {
    fetchMock.mockResolvedValue(new Response("{}", { status: 200 }));

    await apiFetch("/jobs/x/publish", { method: "POST" });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://test.local/api/v1/jobs/x/publish",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
        }),
      }),
    );
  });
});