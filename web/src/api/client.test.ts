import { afterEach, describe, expect, it, vi } from "vitest";

type Seen = { path: string; method: string; csrf: string | null };

/** Loads a fresh copy of the client with a fake fetch (openapi-fetch captures fetch at creation). */
async function loadClient(handler: (request: Request) => Response | Promise<Response>) {
  const seen: Seen[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(new URL(String(input), window.location.href), init);
      seen.push({ path: new URL(request.url).pathname, method: request.method, csrf: request.headers.get("X-CSRF-Token") });
      return handler(request);
    }),
  );
  vi.resetModules();
  return { ...(await import("./client")), seen };
}

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const clearCookie = () => (document.cookie = "pt_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/");

afterEach(() => {
  clearCookie();
  vi.unstubAllGlobals();
});

describe("CSRF protection", () => {
  it("sends the double-submit token on unsafe requests only", async () => {
    document.cookie = "pt_csrf=tok123; path=/";
    const { api, seen } = await loadClient(() => json(200, { ok: true }));
    await api.GET("/api/v1/meta");
    await api.POST("/api/v1/auth/logout");
    expect(seen).toEqual([
      { path: "/api/v1/meta", method: "GET", csrf: null },
      { path: "/api/v1/auth/logout", method: "POST", csrf: "tok123" },
    ]);
  });

  it("fetches a token first when the cookie is missing", async () => {
    const { api, seen } = await loadClient((request) => {
      if (new URL(request.url).pathname === "/api/v1/auth/csrf") document.cookie = "pt_csrf=fresh; path=/";
      return json(200, { ok: true });
    });
    await api.POST("/api/v1/auth/logout");
    expect(seen.map((s) => s.path)).toEqual(["/api/v1/auth/csrf", "/api/v1/auth/logout"]);
    expect(seen[1]!.csrf).toBe("fresh");
  });
});

describe("unwrap", () => {
  it("raises the server's error code and message", async () => {
    const { api, unwrap, ApiError } = await loadClient(() => json(409, { code: "run_in_progress", message: "Já existe uma busca em andamento.", details: null }));
    const failure = unwrap(api.POST("/api/v1/runs", { body: {} }));
    await expect(failure).rejects.toBeInstanceOf(ApiError);
    await expect(unwrap(api.POST("/api/v1/runs", { body: {} }))).rejects.toMatchObject({ status: 409, code: "run_in_progress", message: "Já existe uma busca em andamento." });
  });

  it("explains failures without a JSON body in plain Portuguese", async () => {
    const { api, unwrap, errorMessage } = await loadClient(() => new Response("upstream down", { status: 502 }));
    await expect(unwrap(api.GET("/api/v1/meta"))).rejects.toMatchObject({ status: 502, message: expect.stringContaining("servidor encontrou um erro") });
    expect(errorMessage(new TypeError("Failed to fetch"))).toContain("Sem conexão");
  });
});
