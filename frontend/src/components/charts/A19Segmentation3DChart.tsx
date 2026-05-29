"use client";

/**
 * A19 — Customer Segmentation 3D cluster scatter.
 *
 * Renders each K-Means cluster as a halo of customer-points around the
 * cluster centroid, in (Recency × Frequency × Monetary) space. The
 * actual A19 result_json gives us:
 *   - `clusters`: per-cluster aggregate (centroid + avg R/F/M + revenue)
 *   - `top_customers_per_cluster`: a few representative customers per cluster
 *
 * We plot:
 *   - Large emissive spheres at each cluster centroid
 *   - Small spheres for each top customer in that cluster
 *   - All axes labelled R / F / M
 *
 * Axes are min-max scaled into a 0..5 box so the scene fits regardless of
 * the data's absolute magnitudes (recency can be 0–1000 days, monetary
 * 0–100k, frequency 1–50 — without scaling the chart would be invisible).
 */

import { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Text } from "@react-three/drei";
import * as THREE from "three";
import { InsightCard } from "./foundation/InsightCard";
import { DecisionCardShell } from "./foundation/DecisionCardShell";
import { AIInsightPanel } from "./foundation/AIInsightPanel";
import { ActionChipRow, type SuggestedAction } from "./foundation/ActionChipRow";
import { paletteColor, NoDataState } from "./chartHelpers";

interface Centroid { recency_days: number; frequency: number; monetary: number; }
interface Cluster { cluster_id: number; label: string; name?: string; count: number; pct: number; centroid: Centroid; avg_monetary: number; }
interface TopCustomer { customer_id: string; recency_days: number; frequency: number; monetary: number; }
interface TopPerCluster { cluster_id: number; customers: TopCustomer[]; }

interface A19Data {
  clusters?: Cluster[];
  top_customers_per_cluster?: TopPerCluster[];
}

interface Props { data: A19Data; moduleKey: string; }

function AxisFrame() {
  return (
    <group>
      <mesh position={[3, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.015, 0.015, 6, 8]} />
        <meshBasicMaterial color="#ef4444" />
      </mesh>
      <Text position={[5.8, 0, 0]} fontSize={0.35} color="#ef4444">Recency</Text>
      <mesh position={[0, 3, 0]}>
        <cylinderGeometry args={[0.015, 0.015, 6, 8]} />
        <meshBasicMaterial color="#22c55e" />
      </mesh>
      <Text position={[0, 5.8, 0]} fontSize={0.35} color="#22c55e">Frequency</Text>
      <mesh position={[0, 0, 3]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.015, 0.015, 6, 8]} />
        <meshBasicMaterial color="#3b82f6" />
      </mesh>
      <Text position={[0, 0, 5.8]} fontSize={0.35} color="#3b82f6">Monetary</Text>
    </group>
  );
}

function SubtleSpin({ children }: { children: React.ReactNode }) {
  const ref = useRef<THREE.Group>(null);
  useFrame((_, delta) => { if (ref.current) ref.current.rotation.y += delta * 0.04; });
  return <group ref={ref}>{children}</group>;
}

export function A19Segmentation3DChart({ data }: Props) {
  const clusters = data?.clusters || [];
  const topPerCluster = data?.top_customers_per_cluster || [];

  const projected = useMemo(() => {
    if (clusters.length === 0) {
      return { centroids: [] as Array<Cluster & { x: number; y: number; z: number }>, customers: [] as Array<TopCustomer & { x: number; y: number; z: number; cluster_id: number }> };
    }
    const allR: number[] = [];
    const allF: number[] = [];
    const allM: number[] = [];
    clusters.forEach((c) => {
      allR.push(c.centroid.recency_days);
      allF.push(c.centroid.frequency);
      allM.push(c.centroid.monetary);
    });
    topPerCluster.forEach((g) => g.customers.forEach((cust) => {
      allR.push(cust.recency_days);
      allF.push(cust.frequency);
      allM.push(cust.monetary);
    }));
    const minR = Math.min(...allR), maxR = Math.max(...allR);
    const minF = Math.min(...allF), maxF = Math.max(...allF);
    const minM = Math.min(...allM), maxM = Math.max(...allM);
    const scale = (v: number, lo: number, hi: number) => hi === lo ? 2.5 : ((v - lo) / (hi - lo)) * 5;

    const centroids = clusters.map((c) => ({
      ...c,
      x: scale(c.centroid.recency_days, minR, maxR),
      y: scale(c.centroid.frequency, minF, maxF),
      z: scale(c.centroid.monetary, minM, maxM),
    }));
    const customers = topPerCluster.flatMap((g) =>
      g.customers.map((cust) => ({
        ...cust,
        cluster_id: g.cluster_id,
        x: scale(cust.recency_days, minR, maxR),
        y: scale(cust.frequency, minF, maxF),
        z: scale(cust.monetary, minM, maxM),
      })),
    );
    return { centroids, customers };
  }, [clusters, topPerCluster]);

  const a19Headline = (data as any)?.headline ?? {};
  const a19Question = (data as any)?.question || "How do my customers naturally group together?";
  const a19Actions = (data as any)?.suggested_actions || [];
  const a19ModuleKey = "A19";

  if (clusters.length === 0) {
    return (
      <DecisionCardShell
        moduleKey={a19ModuleKey}
        question={a19Question}
        period="no data"
        headlineValue="—"
        headlineLabel="natural customer clusters"
        aiInsight={<AIInsightPanel moduleKey={a19ModuleKey} question={a19Question} data={data} />}
        actions={<ActionChipRow actions={a19Actions as SuggestedAction[]} />}
      >
        <NoDataState message="No segmentation data" />
      </DecisionCardShell>
    );
  }

  const largestCluster = clusters.reduce((a, b) => (a.count > b.count ? a : b));

  return (
    <DecisionCardShell
      moduleKey={a19ModuleKey}
      question={a19Question}
      period={a19Headline.period || `${clusters.length} clusters identified`}
      headlineValue={String(a19Headline.value ?? clusters.length)}
      headlineLabel={a19Headline.label || `natural customer clusters · largest: ${largestCluster.label || largestCluster.name || `Cluster ${largestCluster.cluster_id}`}`}
      aiInsight={<AIInsightPanel moduleKey={a19ModuleKey} question={a19Question} data={data} />}
      actions={<ActionChipRow actions={a19Actions as SuggestedAction[]} />}
    >
      <div className="flex flex-col lg:flex-row gap-6">
        <div className="flex-1 min-w-0 h-[400px] relative bg-slate-50/50 dark:bg-black/20 rounded-xl overflow-hidden border border-slate-100 dark:border-white/5">
          <Canvas camera={{ position: [8, 6, 8], fov: 50 }} dpr={[1, 2]} style={{ background: "transparent" }}>
            <ambientLight intensity={0.7} />
            <pointLight position={[10, 10, 10]} intensity={0.8} />
            <pointLight position={[-10, -5, -10]} intensity={0.3} />

            <SubtleSpin>
              <AxisFrame />
              <gridHelper args={[6, 6, "#e2e8f0", "rgba(148,163,184,0.1)"]} position={[3, 0, 3]} />
            </SubtleSpin>

            {projected.centroids.map((c) => (
              <group key={`centroid-${c.cluster_id}`}>
                <mesh position={[c.x, c.y, c.z]}>
                  <sphereGeometry args={[0.3, 16, 16]} />
                  <meshStandardMaterial color={paletteColor(c.cluster_id)} emissive={paletteColor(c.cluster_id)} emissiveIntensity={0.5} />
                </mesh>
                <Text position={[c.x, c.y + 0.5, c.z]} fontSize={0.22} color="#64748b" anchorX="center">{c.name || c.label}</Text>
              </group>
            ))}

            {projected.customers.map((cust) => (
              <mesh key={cust.customer_id} position={[cust.x, cust.y, cust.z]}>
                <sphereGeometry args={[0.09, 10, 10]} />
                <meshStandardMaterial color={paletteColor(cust.cluster_id)} emissive={paletteColor(cust.cluster_id)} emissiveIntensity={0.2} />
              </mesh>
            ))}

            <OrbitControls enablePan={false} minDistance={4} maxDistance={20} target={[2.5, 2.5, 2.5]} />
          </Canvas>
          <div className="absolute bottom-3 left-3 text-[10px] font-medium text-slate-500 bg-white/80 dark:bg-black/60 rounded-md px-2 py-1 backdrop-blur border border-slate-200 dark:border-white/10 shadow-sm">
            Drag to rotate · Scroll to zoom
          </div>
        </div>

        <aside className="w-full lg:w-64 flex-shrink-0 flex flex-col gap-3">
          <p className="text-[10px] text-slate-500 uppercase tracking-wider font-medium mb-1">Identified Clusters</p>
          <div className="space-y-2.5">
            {clusters.map((c) => (
              <div key={c.cluster_id} className="bg-slate-50/80 dark:bg-white/[0.02] border border-slate-100 dark:border-white/5 rounded-lg p-3 hover:bg-slate-100 dark:hover:bg-white/[0.04] transition-colors group">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: paletteColor(c.cluster_id), boxShadow: `0 0 6px ${paletteColor(c.cluster_id)}` }} />
                  <span className="text-sm font-semibold text-slate-800 dark:text-slate-200 truncate">{c.name || c.label}</span>
                </div>
                <div className="pl-4 flex items-center justify-between">
                  <span className="text-xs font-medium text-slate-500">{c.count.toLocaleString()} customers</span>
                  <span className="text-xs font-bold text-slate-600 dark:text-slate-400">{c.pct.toFixed(1)}%</span>
                </div>
              </div>
            ))}
          </div>
        </aside>
      </div>
    </DecisionCardShell>
  );
}
