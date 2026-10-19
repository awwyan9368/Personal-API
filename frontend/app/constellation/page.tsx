"use client";

import React, { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Node,
  Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Network,
  Search,
  RotateCcw,
  ExternalLink,
  Info,
} from "lucide-react";

const ENTITY_TYPES = [
  { key: "habit", label: "Habits", color: "#8b5cf6" },
  { key: "goal", label: "Goals", color: "#10b981" },
  { key: "project", label: "Projects", color: "#06b6d4" },
  { key: "activity_category", label: "Activity Cats", color: "#3b82f6" },
  { key: "spending_category", label: "Spending Cats", color: "#f43f5e" },
  { key: "application", label: "Apps", color: "#f59e0b" },
  { key: "time_period", label: "Time Periods", color: "#64748b" },
  { key: "wellbeing_metric", label: "Wellbeing", color: "#14b8a6" },
  { key: "milestone", label: "Milestones", color: "#84cc16" },
];

export default function PersonalDataConstellationPage() {
  const [graphData, setGraphData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [selectedNode, setSelectedNode] = useState<any | null>(null);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  async function loadGraph() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search.trim()) params.set("search", search.trim());
      if (selectedTypes.length > 0) params.set("entity_types", selectedTypes.join(","));
      if (startDate) params.set("start_date", startDate);
      if (endDate) params.set("end_date", endDate);
      const res = await apiFetch(`/constellation?${params.toString()}`);
      setGraphData(res);
      if (res?.nodes?.length > 0 && !selectedNode) {
        setSelectedNode(res.nodes[0]);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadGraph();
  }, [search, selectedTypes, startDate, endDate]);

  function toggleType(t: string) {
    setSelectedTypes((prev) =>
      prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]
    );
  }

  function resetAll() {
    setSearch("");
    setSelectedTypes([]);
    setStartDate("");
    setEndDate("");
    setSelectedNode(null);
  }

  const rfNodes: Node[] = useMemo(() => {
    return (graphData?.nodes || []).map((nd: any) => {
      const isSelected = selectedNode?.id === nd.id;
      return {
        id: nd.id,
        position: nd.position || { x: 400, y: 300 },
        data: {
          label: (
            <div className="text-left">
              <div className="flex items-center gap-1.5">
                <span
                  className="h-2 w-2 rounded-full shrink-0"
                  style={{ backgroundColor: nd.color }}
                />
                <span className="font-bold text-[11px] text-white truncate">
                  {nd.label}
                </span>
              </div>
              {nd.subtitle && (
                <div className="mt-0.5 text-[9px] text-gray-300 truncate">
                  {nd.subtitle}
                </div>
              )}
            </div>
          ),
          raw: nd,
        },
        style: {
          background: isSelected ? "#1e1b4b" : "#12141c",
          border: isSelected ? `2px solid ${nd.color}` : `1px solid ${nd.color}66`,
          borderRadius: "10px",
          padding: "8px 10px",
          width: 175,
          boxShadow: isSelected ? `0 0 16px ${nd.color}44` : "none",
        },
      };
    });
  }, [graphData, selectedNode]);

  const rfEdges: Edge[] = useMemo(() => {
    return (graphData?.edges || []).map((ed: any) => {
      const isConnected =
        selectedNode &&
        (ed.source === selectedNode.id || ed.target === selectedNode.id);
      return {
        id: ed.id,
        source: ed.source,
        target: ed.target,
        label: isConnected ? ed.label : undefined,
        animated: Boolean(isConnected),
        style: {
          stroke: isConnected ? "#8b5cf6" : "#334155",
          strokeWidth: isConnected ? 2.2 : 1.1,
          opacity: selectedNode ? (isConnected ? 1 : 0.35) : 0.75,
        },
        labelStyle: { fill: "#e2e8f0", fontSize: 9, fontWeight: 600 },
        labelBgStyle: { fill: "#0f172a", fillOpacity: 0.85 },
      };
    });
  }, [graphData, selectedNode]);

  const connectedEdges = useMemo(() => {
    if (!selectedNode || !graphData?.edges) return [];
    return graphData.edges.filter(
      (e: any) => e.source === selectedNode.id || e.target === selectedNode.id
    );
  }, [graphData, selectedNode]);

  return (
    <div className="space-y-5">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Personal Data Constellation</h1>
          <p className="text-sm text-muted-foreground">
            Interactive knowledge graph connecting your habits, goals, projects, categories, apps, and wellbeing
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-lg border border-border bg-card px-3 py-1.5 text-xs">
            <strong>{graphData?.summary?.total_nodes || 0}</strong> nodes ·{" "}
            <strong>{graphData?.summary?.total_edges || 0}</strong> relationships
          </span>
          <button
            onClick={resetAll}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-medium hover:bg-secondary"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Reset View
          </button>
        </div>
      </div>

      {/* Controls Bar */}
      <div className="rounded-xl border border-border bg-card p-4 space-y-3">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
          <div className="relative sm:col-span-2">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search nodes and 1-hop neighbors..."
              className="w-full rounded-lg border border-border bg-background pl-9 pr-3 py-2 text-xs"
            />
          </div>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="rounded-lg border border-border bg-background px-3 py-2 text-xs"
          />
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="rounded-lg border border-border bg-background px-3 py-2 text-xs"
          />
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          {ENTITY_TYPES.map((et) => {
            const active = selectedTypes.includes(et.key);
            return (
              <button
                key={et.key}
                onClick={() => toggleType(et.key)}
                className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium transition ${
                  active
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary text-muted-foreground hover:text-foreground"
                }`}
              >
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ backgroundColor: et.color }}
                />
                {et.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Graph + Inspector Layout */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-4">
        <div className="h-[580px] overflow-hidden rounded-xl border border-border bg-[#0b0d13] lg:col-span-3">
          {loading ? (
            <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
              Computing personal knowledge graph...
            </div>
          ) : graphData?.summary?.is_empty ? (
            <div className="flex h-full flex-col items-center justify-center p-8 text-center">
              <Network className="h-10 w-10 text-primary" />
              <h3 className="mt-3 text-sm font-semibold">Constellation awaits your records</h3>
              <p className="mt-1 max-w-md text-xs text-muted-foreground">
                {graphData?.summary?.empty_state_explanation}
              </p>
            </div>
          ) : (
            <ReactFlow
              nodes={rfNodes}
              edges={rfEdges}
              onNodeClick={(_, node) => setSelectedNode(node.data.raw)}
              fitView
              minZoom={0.25}
              maxZoom={2}
            >
              <Background color="#1e293b" gap={20} />
              <Controls />
              <MiniMap
                nodeColor={(n: any) => n.data?.raw?.color || "#8b5cf6"}
                maskColor="rgba(11, 13, 19, 0.75)"
                style={{ backgroundColor: "#11131a" }}
              />
            </ReactFlow>
          )}
        </div>

        {/* Node Detail & Relationship Explanation Panel */}
        <div className="flex flex-col justify-between rounded-xl border border-border bg-card p-5">
          {selectedNode ? (
            <div className="space-y-4">
              <div>
                <div className="flex items-center gap-2">
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: selectedNode.color }}
                  />
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    {selectedNode.entity_type.replace("_", " ")}
                  </span>
                </div>
                <h3 className="mt-1 text-base font-bold">{selectedNode.label}</h3>
                {selectedNode.subtitle && (
                  <p className="text-xs text-muted-foreground">{selectedNode.subtitle}</p>
                )}
              </div>

              {selectedNode.metrics && (
                <div className="space-y-1.5 rounded-lg border border-border/60 bg-secondary/20 p-3 text-xs">
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Node Metrics
                  </div>
                  {Object.entries(selectedNode.metrics).map(([k, v]) => (
                    <div key={k} className="flex items-center justify-between">
                      <span className="text-muted-foreground">{k.replace(/_/g, " ")}</span>
                      <span className="font-mono font-semibold">{String(v)}</span>
                    </div>
                  ))}
                </div>
              )}

              <div>
                <div className="mb-2 text-xs font-semibold">
                  Relationships ({connectedEdges.length})
                </div>
                <div className="max-h-60 space-y-2 overflow-y-auto pr-1 text-xs">
                  {connectedEdges.length === 0 ? (
                    <p className="text-muted-foreground">
                      No direct edges in current filter view.
                    </p>
                  ) : (
                    connectedEdges.map((edge: any) => (
                      <div
                        key={edge.id}
                        className="rounded-lg border border-border/60 bg-secondary/30 p-2.5"
                      >
                        <div className="font-semibold text-primary capitalize">
                          {edge.label}
                        </div>
                        <p className="mt-0.5 text-[11px] leading-relaxed text-muted-foreground">
                          {edge.explanation}
                        </p>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {selectedNode.link && (
                <Link
                  href={selectedNode.link}
                  className="inline-flex w-full items-center justify-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground hover:opacity-90"
                >
                  <span>Open Domain View</span>
                  <ExternalLink className="h-3.5 w-3.5" />
                </Link>
              )}
            </div>
          ) : (
            <div className="flex h-full flex-col items-center justify-center text-center text-xs text-muted-foreground">
              <Info className="mb-2 h-6 w-6 text-primary" />
              <p>Click any node in the Constellation to inspect its metrics and exact relationship explanations.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

