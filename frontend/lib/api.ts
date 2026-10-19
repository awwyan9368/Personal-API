export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api/v1";

const TOKEN_STORAGE_KEY = "plos_auth_token";

// Instant in-memory GET cache for zero-latency tab switching, invalidated on any mutation
const GET_CACHE = new Map<string, { data: any; timestamp: number }>();
const IN_FLIGHT = new Map<string, Promise<any>>();
const CACHE_TTL_MS = 15_000;

export function clearApiCache(): void {
  GET_CACHE.clear();
  IN_FLIGHT.clear();
}

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setStoredToken(token: string | null): void {
  if (typeof window === "undefined") return;
  clearApiCache();
  if (token) {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  } else {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}

export async function apiFetch<T = any>(
  path: string,
  options: RequestInit = {},
  overrideToken?: string
): Promise<T> {
  const method = (options.method || "GET").toUpperCase();
  const token = overrideToken || getStoredToken();

  const normalizedPath = path.startsWith("http")
    ? path
    : path.startsWith("/api/v1")
    ? path
    : `${API_BASE}${path.startsWith("/") ? "" : "/"}${path}`;

  // Any write operation immediately invalidates cached GET responses so data is always fresh
  if (method !== "GET") {
    clearApiCache();
  } else if (!overrideToken) {
    const cached = GET_CACHE.get(normalizedPath);
    const now = Date.now();
    if (cached && now - cached.timestamp < CACHE_TTL_MS) {
      return cached.data as T;
    }
    const existingPromise = IN_FLIGHT.get(normalizedPath);
    if (existingPromise) {
      return existingPromise as Promise<T>;
    }
  }

  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  if (options.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const fetchPromise = (async () => {
    try {
      const response = await fetch(normalizedPath, {
        ...options,
        headers,
        credentials: "include",
      });

      if (response.status === 204) {
        return null as T;
      }

      const contentType = response.headers.get("content-type") || "";
      const isJson = contentType.includes("application/json");
      const payload = isJson ? await response.json() : await response.text();

      if (!response.ok) {
        const detail =
          isJson && payload && typeof payload === "object" && "detail" in payload
            ? typeof payload.detail === "string"
              ? payload.detail
              : JSON.stringify(payload.detail)
            : `Request failed with HTTP ${response.status}`;
        const err = new Error(detail) as Error & { status?: number; payload?: any };
        err.status = response.status;
        err.payload = payload;
        throw err;
      }

      if (method === "GET" && !overrideToken) {
        GET_CACHE.set(normalizedPath, { data: payload, timestamp: Date.now() });
      }

      return payload as T;
    } finally {
      if (method === "GET") {
        IN_FLIGHT.delete(normalizedPath);
      }
    }
  })();

  if (method === "GET" && !overrideToken) {
    IN_FLIGHT.set(normalizedPath, fetchPromise);
  }

  return fetchPromise;
}
