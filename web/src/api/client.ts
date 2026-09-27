import createClient, { type Middleware } from "openapi-fetch";
import type { components, paths } from "./schema";

export type Schemas = components["schemas"];

export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);

function readCookie(name: string): string | undefined {
  return document.cookie
    .split("; ")
    .find((row) => row.startsWith(`${name}=`))
    ?.split("=")[1];
}

let csrfPromise: Promise<void> | null = null;

async function ensureCsrf(): Promise<string | undefined> {
  if (!readCookie("pt_csrf")) {
    csrfPromise ??= fetch("/api/v1/auth/csrf", { credentials: "same-origin" }).then(() => undefined);
    await csrfPromise;
    csrfPromise = null;
  }
  return readCookie("pt_csrf");
}

const csrfMiddleware: Middleware = {
  async onRequest({ request }) {
    if (UNSAFE.has(request.method)) {
      const token = await ensureCsrf();
      if (token) request.headers.set("X-CSRF-Token", token);
    }
    return request;
  },
};

// Same-origin API behind the web server; an absolute base also works where Request needs one (tests).
export const api = createClient<paths>({ baseUrl: globalThis.location?.origin ?? "", credentials: "same-origin" });
api.use(csrfMiddleware);

type Result<T> = { data?: T; error?: unknown; response: Response };

/** Unwrap an openapi-fetch result, throwing a typed ApiError on failure. */
export async function unwrap<T>(promise: Promise<Result<T>>): Promise<T> {
  const { data, error, response } = await promise;
  if (!response.ok || error !== undefined) {
    const body = (error ?? {}) as { code?: string; message?: string; details?: unknown };
    throw new ApiError(
      response.status,
      body.code ?? "http_error",
      body.message ?? friendlyStatus(response.status),
      body.details,
    );
  }
  return data as T;
}

function friendlyStatus(status: number): string {
  if (status === 0) return "Sem conexão com o servidor.";
  if (status >= 500) return "O servidor encontrou um erro. Tente novamente em instantes.";
  if (status === 404) return "Não encontrado.";
  if (status === 401) return "Entre na sua conta para continuar.";
  return "Não foi possível concluir a ação.";
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof TypeError) return "Sem conexão com o servidor. Verifique a rede e tente novamente.";
  return "Algo deu errado. Tente novamente.";
}

/** Multipart upload (openapi-fetch keeps JSON as the default body serializer). */
export async function uploadImage(path: string, file: File): Promise<unknown> {
  const token = await ensureCsrf();
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(path, {
    method: "POST",
    body: form,
    credentials: "same-origin",
    headers: token ? { "X-CSRF-Token": token } : {},
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ApiError(response.status, body.code ?? "http_error", body.message ?? friendlyStatus(response.status), body.details);
  }
  return body;
}
