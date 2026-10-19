"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import {
  Terminal,
  Key,
  Play,
  Copy,
  Check,
  ShieldAlert,
  Trash2,
  Plug,
  Code2,
} from "lucide-react";

export default function ApiConsolePage() {
  const [tokens, setTokens] = useState<any[]>([]);
  const [catalog, setCatalog] = useState<any>(null);
  const [integrations, setIntegrations] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  // Create Token state
  const [tokenName, setTokenName] = useState("Local Automation Script");
  const [selectedScopes, setSelectedScopes] = useState<string[]>(["read:all", "write:all"]);
  const [expiresDays, setExpiresDays] = useState("90");
  const [newlyCreatedToken, setNewlyCreatedToken] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Interactive API Playground state
  const [playMethod, setPlayMethod] = useState("GET");
  const [playPath, setPlayPath] = useState("/api/v1/dashboard");
  const [playBody, setPlayBody] = useState("");
  const [playCustomToken, setPlayCustomToken] = useState("");
  const [playResponse, setPlayResponse] = useState<any>(null);
  const [playStatus, setPlayStatus] = useState<number | null>(null);
  const [playDurationMs, setPlayDurationMs] = useState<number | null>(null);
  const [playLoading, setPlayLoading] = useState(false);

  // Code snippet tab
  const [snippetLang, setSnippetLang] = useState<"curl" | "python" | "js" | "powershell">("python");

  async function loadAll() {
    setLoading(true);
    try {
      const [tokRes, catRes, intRes] = await Promise.all([
        apiFetch("/tokens"),
        apiFetch("/catalog"),
        apiFetch("/integrations"),
      ]);
      setTokens(tokRes || []);
      setCatalog(catRes);
      setIntegrations(intRes);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  async function handleCreateToken(e: React.FormEvent) {
    e.preventDefault();
    if (!tokenName.trim()) return;
    try {
      const res = await apiFetch("/tokens", {
        method: "POST",
        body: JSON.stringify({
          name: tokenName.trim(),
          scopes: selectedScopes,
          expires_in_days: expiresDays ? Number(expiresDays) : null,
        }),
      });
      setNewlyCreatedToken(res.raw_token);
      setPlayCustomToken(res.raw_token);
      await loadAll();
    } catch (err: any) {
      alert(err.message || "Failed to generate token");
    }
  }

  async function handleRevokeToken(id: string) {
    if (!confirm("Revoke this personal API token immediately?")) return;
    try {
      await apiFetch(`/tokens/${id}/revoke`, { method: "POST" });
      await loadAll();
    } catch (err: any) {
      alert(err.message || "Failed to revoke token");
    }
  }

  async function handleDeleteToken(id: string) {
    try {
      await apiFetch(`/tokens/${id}`, { method: "DELETE" });
      await loadAll();
    } catch (err: any) {
      alert(err.message || "Failed to delete token");
    }
  }

  async function handleRunPlayground(e: React.FormEvent) {
    e.preventDefault();
    setPlayLoading(true);
    setPlayResponse(null);
    const t0 = performance.now();
    try {
      const headers: Record<string, string> = {};
      if (playCustomToken.trim()) {
        headers["Authorization"] = `Bearer ${playCustomToken.trim()}`;
      }
      if (playMethod !== "GET" && playMethod !== "DELETE" && playBody.trim()) {
        headers["Content-Type"] = "application/json";
      }

      const res = await fetch(playPath, {
        method: playMethod,
        headers,
        credentials: "include",
        body:
          playMethod !== "GET" && playMethod !== "DELETE" && playBody.trim()
            ? playBody
            : undefined,
      });
      const elapsed = Math.round(performance.now() - t0);
      setPlayDurationMs(elapsed);
      setPlayStatus(res.status);
      const text = await res.text();
      try {
        setPlayResponse(JSON.parse(text));
      } catch {
        setPlayResponse(text);
      }
    } catch (err: any) {
      setPlayStatus(500);
      setPlayResponse({ error: err.message });
    } finally {
      setPlayLoading(false);
    }
  }

  function selectEndpointFromCatalog(ep: any) {
    setPlayMethod(ep.method);
    setPlayPath(ep.path);
    setPlayBody(ep.sample_body ? JSON.stringify(ep.sample_body, null, 2) : "");
  }

  const supportedScopes: string[] = catalog?.supported_scopes || [
    "read:all",
    "write:all",
    "read:habits",
    "write:habits",
    "read:finance",
    "write:finance",
    "read:screen_time",
    "write:screen_time",
    "read:activities",
    "write:activities",
    "read:goals",
    "write:goals",
    "read:journal",
    "write:journal",
    "read:wellbeing",
    "write:wellbeing",
    "read:analytics",
    "write:imports",
    "read:exports",
  ];

  const exampleToken = playCustomToken || "plos_your_personal_token_here";
  const snippets: Record<string, string> = {
    python: `import httpx

TOKEN = "${exampleToken}"
BASE_URL = "http://localhost:8000"

headers = {"Authorization": f"Bearer {TOKEN}"}
response = httpx.request("${playMethod}", f"{BASE_URL}${playPath}", headers=headers${
      playBody ? `, json=${playBody}` : ""
    })
print(response.status_code)
print(response.json())`,
    curl: `curl -X ${playMethod} "http://localhost:8000${playPath}" \\
  -H "Authorization: Bearer ${exampleToken}" \\
  -H "Content-Type: application/json"${playBody ? ` \\\n  -d '${playBody}'` : ""}`,
    js: `const response = await fetch("http://localhost:8000${playPath}", {
  method: "${playMethod}",
  headers: {
    "Authorization": "Bearer ${exampleToken}",
    "Content-Type": "application/json"
  }${playBody ? `,\n  body: JSON.stringify(${playBody})` : ""}
});
const data = await response.json();
console.log(data);`,
    powershell: `$headers = @{
    "Authorization" = "Bearer ${exampleToken}"
    "Content-Type"  = "application/json"
}
Invoke-RestMethod -Method ${playMethod} -Uri "http://localhost:8000${playPath}" -Headers $headers${
      playBody ? ` -Body '${playBody}'` : ""
    }`,
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Personal REST API & Integrations Center</h1>
        <p className="text-sm text-muted-foreground">
          Manage scoped <code className="text-primary">plos_</code> tokens, test real endpoints in the live API Playground, and inspect local adapters
        </p>
      </div>

      {/* Newly Created Token One-Time Banner */}
      {newlyCreatedToken && (
        <div className="rounded-xl border border-accent/50 bg-accent/10 p-4 text-xs">
          <div className="flex items-center justify-between">
            <span className="font-bold text-accent">
              New Personal API Token Generated (Copy now — shown only once, stored as SHA-256 hash):
            </span>
            <button
              onClick={() => {
                navigator.clipboard.writeText(newlyCreatedToken);
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
              }}
              className="inline-flex items-center gap-1 rounded-lg bg-accent px-3 py-1 font-semibold text-black"
            >
              {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
              {copied ? "Copied" : "Copy Token"}
            </button>
          </div>
          <div className="mt-2 rounded bg-background p-2.5 font-mono text-sm font-bold text-foreground select-all">
            {newlyCreatedToken}
          </div>
        </div>
      )}

      {/* Token Management + Create Token */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <form
          onSubmit={handleCreateToken}
          className="rounded-xl border border-border bg-card p-5 space-y-3 text-xs"
        >
          <div className="flex items-center gap-2 text-sm font-bold">
            <Key className="h-4 w-4 text-primary" />
            <span>Create Personal API Token</span>
          </div>
          <div>
            <label className="mb-1 block font-medium">Token Label</label>
            <input
              type="text"
              required
              value={tokenName}
              onChange={(e) => setTokenName(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3 py-2"
            />
          </div>
          <div>
            <label className="mb-1 block font-medium">Expiration (Days)</label>
            <input
              type="number"
              min="1"
              max="3650"
              value={expiresDays}
              onChange={(e) => setExpiresDays(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3 py-2"
            />
          </div>
          <div>
            <label className="mb-1 block font-medium">Granted Scopes</label>
            <div className="max-h-36 space-y-1 overflow-y-auto rounded-lg border border-border bg-background p-2">
              {supportedScopes.map((sc) => (
                <label key={sc} className="flex items-center gap-2 font-mono text-[11px]">
                  <input
                    type="checkbox"
                    checked={selectedScopes.includes(sc)}
                    onChange={(e) =>
                      setSelectedScopes((prev) =>
                        e.target.checked ? [...prev, sc] : prev.filter((x) => x !== sc)
                      )
                    }
                  />
                  <span>{sc}</span>
                </label>
              ))}
            </div>
          </div>
          <button
            type="submit"
            className="w-full rounded-lg bg-primary py-2 font-semibold text-primary-foreground hover:opacity-90"
          >
            Generate Scoped Token
          </button>
        </form>

        {/* Active Tokens List */}
        <div className="rounded-xl border border-border bg-card p-5 lg:col-span-2">
          <h3 className="text-sm font-bold">Issued Personal API Tokens</h3>
          <p className="text-xs text-muted-foreground">
            Tokens are hashed with SHA-256 at rest and can be revoked at any time
          </p>
          <div className="mt-4 space-y-2.5 text-xs">
            {tokens.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border py-10 text-center text-muted-foreground">
                No personal API tokens issued yet.
              </div>
            ) : (
              tokens.map((t) => (
                <div
                  key={t.id}
                  className="flex flex-col justify-between gap-3 rounded-lg border border-border/60 bg-secondary/20 p-3.5 sm:flex-row sm:items-center"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold">{t.name}</span>
                      <code className="rounded bg-background px-2 py-0.5 text-[11px] text-primary">
                        {t.token_prefix}...
                      </code>
                      {t.is_revoked ? (
                        <span className="rounded bg-destructive/15 px-2 py-0.5 text-[10px] font-semibold text-destructive">
                          Revoked
                        </span>
                      ) : (
                        <span className="rounded bg-accent/15 px-2 py-0.5 text-[10px] font-semibold text-accent">
                          Active
                        </span>
                      )}
                    </div>
                    <div className="mt-1 text-[11px] text-muted-foreground">
                      Scopes: {t.scopes.join(", ")} · Created: {formatDate(t.created_at)}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {!t.is_revoked && (
                      <button
                        onClick={() => handleRevokeToken(t.id)}
                        className="inline-flex items-center gap-1 rounded-lg border border-amber-500/40 bg-amber-500/10 px-2.5 py-1 text-[11px] font-medium text-amber-400"
                      >
                        <ShieldAlert className="h-3 w-3" />
                        Revoke
                      </button>
                    )}
                    <button
                      onClick={() => handleDeleteToken(t.id)}
                      className="rounded p-1.5 text-muted-foreground hover:bg-destructive/15 hover:text-destructive"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Live API Playground + Endpoint Catalog */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="rounded-xl border border-border bg-card p-5">
          <h3 className="text-sm font-bold">Endpoint Catalog</h3>
          <p className="text-xs text-muted-foreground">
            Click any endpoint to load it into the live API Playground
          </p>
          <div className="mt-3 max-h-[460px] space-y-2 overflow-y-auto pr-1 text-xs">
            {(catalog?.endpoints || []).map((ep: any, idx: number) => (
              <button
                key={idx}
                onClick={() => selectEndpointFromCatalog(ep)}
                className="w-full rounded-lg border border-border/60 bg-secondary/20 p-2.5 text-left transition hover:border-primary/50"
              >
                <div className="flex items-center justify-between">
                  <span
                    className={`rounded px-1.5 py-0.5 font-mono text-[10px] font-bold ${
                      ep.method === "GET"
                        ? "bg-sky-500/15 text-sky-400"
                        : "bg-accent/15 text-accent"
                    }`}
                  >
                    {ep.method}
                  </span>
                  <span className="font-mono text-[10px] text-muted-foreground">{ep.scope}</span>
                </div>
                <div className="mt-1 font-mono font-semibold text-foreground">{ep.path}</div>
                <div className="mt-0.5 text-[11px] text-muted-foreground">{ep.summary}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Interactive API Playground */}
        <div className="rounded-xl border border-border bg-card p-5 lg:col-span-2 space-y-4 text-xs">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm font-bold">
              <Terminal className="h-4 w-4 text-primary" />
              <span>Interactive Local API Playground</span>
            </div>
            {playStatus !== null && (
              <div className="flex items-center gap-2 font-mono">
                <span
                  className={`rounded px-2 py-0.5 font-bold ${
                    playStatus < 300
                      ? "bg-accent/15 text-accent"
                      : "bg-destructive/15 text-destructive"
                  }`}
                >
                  HTTP {playStatus}
                </span>
                <span className="text-muted-foreground">{playDurationMs} ms</span>
              </div>
            )}
          </div>

          <form onSubmit={handleRunPlayground} className="space-y-3">
            <div className="flex flex-col gap-2 sm:flex-row">
              <select
                value={playMethod}
                onChange={(e) => setPlayMethod(e.target.value)}
                className="rounded-lg border border-border bg-background px-3 py-2 font-mono font-bold"
              >
                <option value="GET">GET</option>
                <option value="POST">POST</option>
                <option value="PATCH">PATCH</option>
                <option value="DELETE">DELETE</option>
              </select>
              <input
                type="text"
                value={playPath}
                onChange={(e) => setPlayPath(e.target.value)}
                className="flex-1 rounded-lg border border-border bg-background px-3 py-2 font-mono"
              />
              <button
                type="submit"
                disabled={playLoading}
                className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-primary px-4 py-2 font-semibold text-primary-foreground"
              >
                <Play className="h-3.5 w-3.5" />
                {playLoading ? "Sending..." : "Send Request"}
              </button>
            </div>

            <div>
              <label className="mb-1 block font-medium text-muted-foreground">
                Optional Bearer Token Override (leave blank to use current session)
              </label>
              <input
                type="text"
                value={playCustomToken}
                onChange={(e) => setPlayCustomToken(e.target.value)}
                placeholder="plos_..."
                className="w-full rounded-lg border border-border bg-background px-3 py-1.5 font-mono"
              />
            </div>

            {playMethod !== "GET" && playMethod !== "DELETE" && (
              <div>
                <label className="mb-1 block font-medium text-muted-foreground">
                  JSON Request Body
                </label>
                <textarea
                  rows={5}
                  value={playBody}
                  onChange={(e) => setPlayBody(e.target.value)}
                  className="w-full rounded-lg border border-border bg-[#0b0d13] p-3 font-mono text-gray-200"
                />
              </div>
            )}
          </form>

          {/* Response Viewer */}
          <div>
            <div className="mb-1 font-medium text-muted-foreground">Live Backend Response</div>
            <pre className="max-h-64 overflow-y-auto rounded-lg border border-border bg-[#0b0d13] p-3.5 font-mono text-[11px] text-gray-200">
              {playResponse
                ? JSON.stringify(playResponse, null, 2)
                : "// Click 'Send Request' to execute against your local FastAPI server"}
            </pre>
          </div>

          {/* Code Examples */}
          <div className="border-t border-border/60 pt-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="inline-flex items-center gap-1.5 font-semibold">
                <Code2 className="h-3.5 w-3.5 text-primary" />
                Programmatic Code Examples
              </span>
              <div className="flex gap-1">
                {(["python", "curl", "js", "powershell"] as const).map((lang) => (
                  <button
                    key={lang}
                    onClick={() => setSnippetLang(lang)}
                    className={`rounded px-2 py-0.5 text-[10px] font-semibold uppercase ${
                      snippetLang === lang
                        ? "bg-primary text-primary-foreground"
                        : "bg-secondary text-muted-foreground"
                    }`}
                  >
                    {lang}
                  </button>
                ))}
              </div>
            </div>
            <pre className="overflow-x-auto rounded-lg border border-border bg-[#0b0d13] p-3 font-mono text-[11px] text-gray-300">
              {snippets[snippetLang]}
            </pre>
          </div>
        </div>
      </div>

      {/* Local Integrations Status */}
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="flex items-center gap-2 text-sm font-bold">
          <Plug className="h-4 w-4 text-primary" />
          <span>Local-First Adapters & Companion Integrations</span>
        </div>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3 text-xs">
          {(integrations?.integrations || []).map((item: any) => (
            <div
              key={item.id}
              className="rounded-xl border border-border/70 bg-secondary/20 p-4"
            >
              <div className="flex items-center justify-between">
                <span className="font-bold">{item.name}</span>
                <span
                  className={`rounded px-2 py-0.5 text-[10px] font-semibold ${
                    item.is_configured
                      ? "bg-accent/15 text-accent"
                      : "bg-amber-500/15 text-amber-400"
                  }`}
                >
                  {item.status_message}
                </span>
              </div>
              <p className="mt-2 text-muted-foreground leading-relaxed">
                {item.config?.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

