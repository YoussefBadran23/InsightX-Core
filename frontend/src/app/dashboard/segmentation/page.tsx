'use client';

import { useState } from 'react';
import { MoreHorizontal, Plus, Minus, Target, Award, ShieldCheck, AlertOctagon, Focus } from 'lucide-react';

export default function SegmentationPage() {
  const [zoom, setZoom] = useState(1);

  return (
    <div className="flex-1 flex flex-col min-w-0 bg-gray-50 dark:bg-[#0f1115] relative z-0 overflow-hidden animate-fade-in">
      
      {/* Required CSS for 3D Bubbles */}
      <style dangerouslySetInnerHTML={{__html: `
        .bubble-container { perspective: 1000px; }
        .bubble {
            border-radius: 50%;
            position: absolute;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            box-shadow: inset -2px -2px 6px rgba(0,0,0,0.2), inset 2px 2px 6px rgba(255,255,255,0.4), 0 4px 6px rgba(0,0,0,0.1);
            cursor: pointer;
        }
        .dark .bubble {
            box-shadow: inset -2px -2px 6px rgba(0,0,0,0.4), inset 2px 2px 6px rgba(255,255,255,0.25), 0 4px 6px rgba(0,0,0,0.3);
        }
        .bubble:hover {
            transform: scale(1.2) translateZ(20px);
            z-index: 50;
            box-shadow: inset -2px -2px 6px rgba(0,0,0,0.3), inset 2px 2px 6px rgba(255,255,255,0.5), 0 10px 15px rgba(0,0,0,0.2);
        }
        .dark .bubble:hover {
            box-shadow: inset -2px -2px 6px rgba(0,0,0,0.4), inset 2px 2px 6px rgba(255,255,255,0.4), 0 10px 15px rgba(0,0,0,0.5);
        }
        .bubble-gold { background: radial-gradient(circle at 35% 35%, #fcd34d, #b45309); }
        .bubble-blue { background: radial-gradient(circle at 35% 35%, #60a5fa, #1e40af); }
        .bubble-red { background: radial-gradient(circle at 35% 35%, #fca5a5, #991b1b); }
        
        @keyframes custom-float {
            0% { transform: translateY(0px); }
            50% { transform: translateY(-10px); }
            100% { transform: translateY(0px); }
        }
        .cluster-group { animation: custom-float 6s ease-in-out infinite; }
        .cluster-group:nth-child(2) { animation-delay: -2s; }
        .cluster-group:nth-child(3) { animation-delay: -4s; }

        .bg-grid-pattern {
            background-image: linear-gradient(to right, rgba(0,0,0,0.05) 1px, transparent 1px),
                              linear-gradient(to bottom, rgba(0,0,0,0.05) 1px, transparent 1px);
            background-size: 50px 50px;
            mask-image: radial-gradient(circle at center, black 30%, transparent 80%);
            -webkit-mask-image: radial-gradient(circle at center, black 30%, transparent 80%);
        }
        .dark .bg-grid-pattern {
            background-image: linear-gradient(to right, rgba(255,255,255,0.05) 1px, transparent 1px),
                              linear-gradient(to bottom, rgba(255,255,255,0.05) 1px, transparent 1px);
        }
      `}} />

      {/* Controls Overlay Header */}
      <div className="absolute top-0 left-0 w-full p-6 z-20 pointer-events-none">
        <div className="flex flex-col gap-4 pointer-events-auto max-w-[960px]">
          <div className="flex items-end justify-between">
            <div>
              <h1 className="text-gray-900 dark:text-white text-3xl font-bold leading-tight mb-2">Customer Segmentation</h1>
              <p className="text-slate-500 dark:text-[#9da6b9] text-sm">Interactive 3D view clustered by LTV and engagement score.</p>
            </div>
          </div>
          
          <div className="flex gap-3 pt-2">
            <button className="flex h-8 shrink-0 items-center justify-center rounded-lg bg-white dark:bg-[#282e39] hover:bg-gray-50 dark:hover:bg-[#333b49] transition-colors border border-gray-200 dark:border-white/5 px-3 shadow-sm cursor-pointer border-solid">
              <span className="text-gray-700 dark:text-white text-xs font-medium">Date: Last 30 Days</span>
            </button>
            <button className="flex h-8 shrink-0 items-center justify-center rounded-lg bg-white dark:bg-[#282e39] hover:bg-gray-50 dark:hover:bg-[#333b49] transition-colors border border-gray-200 dark:border-white/5 px-3 shadow-sm cursor-pointer border-solid">
              <span className="text-gray-700 dark:text-white text-xs font-medium">Metric: ARR</span>
            </button>
          </div>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden relative">
        <div className="w-full h-full relative cursor-grab active:cursor-grabbing bubble-container">
          {/* Background Grid */}
          <div className="absolute inset-0 bg-grid-pattern opacity-50 dark:opacity-100 pointer-events-none"></div>
          
          {/* Legend */}
          <div className="absolute top-6 right-6 bg-white/70 dark:bg-[#1a1d21]/70 backdrop-blur-md rounded-lg p-4 z-30 shadow-lg border-l-4 border-l-primary hidden md:block">
            <h4 className="text-xs font-bold text-slate-500 dark:text-gray-400 uppercase tracking-wider mb-3">Legend</h4>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-gradient-to-br from-yellow-400 to-yellow-700"></div>
                <span className="text-xs text-gray-800 dark:text-white">Champions (High LTV)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-gradient-to-br from-blue-400 to-blue-800"></div>
                <span className="text-xs text-gray-800 dark:text-white">Loyal (Steady)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-gradient-to-br from-red-400 to-red-800"></div>
                <span className="text-xs text-gray-800 dark:text-white">At-Risk (Churn Likely)</span>
              </div>
            </div>
            <div className="mt-4 pt-3 border-t border-gray-200 dark:border-white/10">
              <span className="text-[10px] text-slate-500">Bubble Size = Revenue</span>
            </div>
          </div>

          {/* 3D Content Container */}
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none" style={{ transform: `scale(${zoom}) translateY(10px)` }}>
            
            {/* Cluster 1: Champions */}
            <div className="absolute top-[20%] right-[25%] w-64 h-64 cluster-group pointer-events-auto">
              <div className="absolute -top-10 left-10 text-amber-500 font-bold text-sm tracking-wide bg-white/80 dark:bg-black/50 px-2 py-1 rounded backdrop-blur-sm border border-amber-500/30 shadow-sm">Champions</div>
              <div className="bubble bubble-gold w-16 h-16 top-0 left-10 opacity-90" title="Acme Corp"></div>
              <div className="bubble bubble-gold w-24 h-24 top-10 left-20 opacity-95 shadow-[0_0_20px_rgba(245,158,11,0.3)] z-10" title="Globex"></div>
              <div className="bubble bubble-gold w-12 h-12 top-24 left-4 opacity-80"></div>
              <div className="bubble bubble-gold w-8 h-8 top-16 left-48 opacity-70"></div>
              <div className="bubble bubble-gold w-14 h-14 top-32 left-32 opacity-85"></div>
              <div className="bubble bubble-gold w-10 h-10 top-5 left-36 opacity-60"></div>
            </div>

            {/* Cluster 2: Loyal */}
            <div className="absolute top-[35%] left-[20%] w-80 h-80 cluster-group pointer-events-auto">
               <div className="absolute -top-8 left-20 text-primary font-bold text-sm tracking-wide bg-white/80 dark:bg-black/50 px-2 py-1 rounded backdrop-blur-sm border border-primary/30 shadow-sm">Loyal Customers</div>
               <div className="bubble bubble-blue w-20 h-20 top-10 left-10 opacity-90 shadow-[0_0_20px_rgba(43,108,238,0.3)] z-10" title="Stark Ind"></div>
               <div className="bubble bubble-blue w-12 h-12 top-0 left-32 opacity-70"></div>
               <div className="bubble bubble-blue w-16 h-16 top-24 left-24 opacity-85"></div>
               <div className="bubble bubble-blue w-10 h-10 top-32 left-5 opacity-60"></div>
               <div className="bubble bubble-blue w-14 h-14 top-16 left-48 opacity-80"></div>
               <div className="bubble bubble-blue w-8 h-8 top-40 left-32 opacity-50"></div>
               <div className="bubble bubble-blue w-24 h-24 top-20 left-60 opacity-60 blur-[1px]"></div>
               <div className="bubble bubble-blue w-6 h-6 top-5 left-50 opacity-40"></div>
            </div>

            {/* Cluster 3: At-Risk */}
            <div className="absolute bottom-[20%] right-[30%] w-72 h-72 cluster-group pointer-events-auto">
               <div className="absolute -top-8 right-10 text-red-500 font-bold text-sm tracking-wide bg-white/80 dark:bg-black/50 px-2 py-1 rounded backdrop-blur-sm border border-red-500/30 shadow-sm">At-Risk</div>
               <div className="bubble bubble-red w-18 h-18 top-10 right-20 opacity-90 shadow-[0_0_20px_rgba(239,68,68,0.3)] z-10" title="Initech"></div>
               <div className="bubble bubble-red w-12 h-12 top-24 right-32 opacity-80"></div>
               <div className="bubble bubble-red w-10 h-10 top-0 right-10 opacity-70"></div>
               <div className="bubble bubble-red w-14 h-14 top-16 right-5 opacity-85"></div>
               <div className="bubble bubble-red w-8 h-8 top-32 right-16 opacity-60"></div>
               <div className="bubble bubble-red w-16 h-16 top-20 right-48 opacity-50 blur-[1px]"></div>
            </div>

          </div>

          <div className="absolute bottom-6 left-6 bg-white/80 dark:bg-[#1a1d21]/80 backdrop-blur rounded-lg flex flex-col p-1 z-30 shadow-md">
            <button onClick={() => setZoom(z => Math.min(1.5, z + 0.1))} className="p-2 text-slate-700 dark:text-white hover:bg-slate-100 dark:hover:bg-white/10 rounded transition-colors" title="Zoom In">
              <Plus className="w-5 h-5" />
            </button>
            <button onClick={() => setZoom(z => Math.max(0.5, z - 0.1))} className="p-2 text-slate-700 dark:text-white hover:bg-slate-100 dark:hover:bg-white/10 rounded transition-colors" title="Zoom Out">
              <Minus className="w-5 h-5" />
            </button>
            <div className="h-px w-full bg-gray-200 dark:bg-white/10 my-1"></div>
            <button onClick={() => setZoom(1)} className="p-2 text-slate-700 dark:text-white hover:bg-slate-100 dark:hover:bg-white/10 rounded transition-colors" title="Reset View">
              <Focus className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Right Sidebar Analytics Overlay */}
        <aside className="hidden xl:flex w-[360px] bg-white dark:bg-[#1a1d21] border-l border-gray-200 dark:border-[#282e39] flex-col shrink-0 z-10 shadow-2xl">
          <div className="p-6 border-b border-gray-200 dark:border-[#282e39]">
            <div className="flex items-center justify-between mb-1">
              <h2 className="text-gray-900 dark:text-white text-lg font-bold">Customer Segments</h2>
              <button className="text-slate-400 hover:text-gray-900 dark:hover:text-white transition-colors cursor-pointer">
                <MoreHorizontal className="w-5 h-5" />
              </button>
            </div>
            <p className="text-slate-500 dark:text-[#9da6b9] text-sm">1,240 Active Users analyzed</p>
            
            <div className="mt-4 flex items-center justify-between bg-gray-50 dark:bg-[#111318] rounded-lg p-3 border border-gray-200 dark:border-[#282e39]">
              <div className="flex flex-col">
                <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide">Total ARR</span>
                <span className="text-gray-900 dark:text-white font-mono text-lg font-medium">$4.2M</span>
              </div>
              <div className="h-8 w-px bg-gray-200 dark:bg-[#282e39]"></div>
              <div className="flex flex-col items-end">
                <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide">Avg Engagement</span>
                <span className="text-emerald-500 font-mono text-lg font-medium">84%</span>
              </div>
            </div>
          </div>
          
          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            <div className="group bg-gray-50 dark:bg-[#22262d] hover:bg-gray-100 dark:hover:bg-[#282e39] border border-transparent hover:border-amber-500/30 rounded-xl p-4 transition-all cursor-pointer relative overflow-hidden shadow-sm">
              <div className="absolute top-0 left-0 w-1 h-full bg-amber-500"></div>
              <div className="flex justify-between items-start mb-3 pl-2">
                <div className="flex items-center gap-2">
                  <Award className="w-5 h-5 text-amber-500" />
                  <h3 className="text-gray-900 dark:text-white font-semibold">Champions</h3>
                </div>
                <span className="bg-amber-100 dark:bg-amber-500/10 text-amber-600 dark:text-amber-500 text-xs px-2 py-1 rounded font-medium">+12% MoM</span>
              </div>
              <div className="pl-2 space-y-3">
                <div className="flex justify-between items-end">
                  <span className="text-3xl font-bold text-gray-900 dark:text-white tracking-tight">150</span>
                  <span className="text-sm text-slate-500 mb-1">Customers</span>
                </div>
                <div className="space-y-1">
                  <div className="flex justify-between text-xs text-slate-500">
                    <span>Avg LTV</span>
                    <span className="text-gray-900 dark:text-white font-mono">$50,200</span>
                  </div>
                  <div className="w-full bg-gray-200 dark:bg-[#111318] rounded-full h-1.5 overflow-hidden">
                    <div className="bg-amber-500 h-full rounded-full" style={{ width: '85%' }}></div>
                  </div>
                </div>
              </div>
            </div>

            <div className="group bg-gray-50 dark:bg-[#22262d] hover:bg-gray-100 dark:hover:bg-[#282e39] border border-transparent hover:border-primary/30 rounded-xl p-4 transition-all cursor-pointer relative overflow-hidden shadow-sm">
               <div className="absolute top-0 left-0 w-1 h-full bg-primary"></div>
               <div className="flex justify-between items-start mb-3 pl-2">
                 <div className="flex items-center gap-2">
                   <ShieldCheck className="w-5 h-5 text-primary" />
                   <h3 className="text-gray-900 dark:text-white font-semibold">Loyal</h3>
                 </div>
                 <span className="bg-blue-100 dark:bg-primary/10 text-primary text-xs px-2 py-1 rounded font-medium">Stable</span>
               </div>
               <div className="pl-2 space-y-3">
                 <div className="flex justify-between items-end">
                   <span className="text-3xl font-bold text-gray-900 dark:text-white tracking-tight">790</span>
                   <span className="text-sm text-slate-500 mb-1">Customers</span>
                 </div>
                 <div className="space-y-1">
                   <div className="flex justify-between text-xs text-slate-500">
                     <span>Avg LTV</span>
                     <span className="text-gray-900 dark:text-white font-mono">$12,400</span>
                   </div>
                   <div className="w-full bg-gray-200 dark:bg-[#111318] rounded-full h-1.5 overflow-hidden">
                     <div className="bg-primary h-full rounded-full" style={{ width: '65%' }}></div>
                   </div>
                 </div>
               </div>
            </div>

            <div className="group bg-gray-50 dark:bg-[#22262d] hover:bg-gray-100 dark:hover:bg-[#282e39] border border-transparent hover:border-red-500/30 rounded-xl p-4 transition-all cursor-pointer relative overflow-hidden shadow-sm">
               <div className="absolute top-0 left-0 w-1 h-full bg-red-500"></div>
               <div className="flex justify-between items-start mb-3 pl-2">
                 <div className="flex items-center gap-2">
                   <AlertOctagon className="w-5 h-5 text-red-500" />
                   <h3 className="text-gray-900 dark:text-white font-semibold">At-Risk</h3>
                 </div>
                 <span className="bg-red-100 dark:bg-red-500/10 text-red-600 dark:text-red-500 text-xs px-2 py-1 rounded font-medium">Attention</span>
               </div>
               <div className="pl-2 space-y-3">
                 <div className="flex justify-between items-end">
                   <span className="text-3xl font-bold text-gray-900 dark:text-white tracking-tight">300</span>
                   <span className="text-sm text-slate-500 mb-1">Customers</span>
                 </div>
                 <div className="bg-red-50 dark:bg-red-900/20 rounded p-2 border border-red-200 dark:border-red-500/10">
                   <div className="flex items-start gap-2">
                     <span className="text-xs text-red-600 dark:text-gray-300">Last active &gt; 90 days ago. Churn probability High.</span>
                   </div>
                 </div>
               </div>
            </div>
          </div>

          <div className="p-6 pt-4 border-t border-gray-200 dark:border-[#282e39] bg-white dark:bg-[#1a1d21]">
            <button className="w-full bg-primary hover:bg-primary-hover text-white font-medium h-12 rounded-lg transition-all shadow-lg shadow-primary/20 flex items-center justify-center gap-2 cursor-pointer">
              <Target className="w-5 h-5" />
              Create Campaign
            </button>
            <div className="mt-3 flex gap-2">
              <button className="flex-1 bg-gray-100 dark:bg-[#282e39] hover:bg-gray-200 dark:hover:bg-[#333b49] text-gray-900 dark:text-white text-sm font-medium h-10 rounded-lg transition-colors border border-gray-200 dark:border-[#3e4552] cursor-pointer">
                 Export
              </button>
              <button className="flex-1 bg-gray-100 dark:bg-[#282e39] hover:bg-gray-200 dark:hover:bg-[#333b49] text-gray-900 dark:text-white text-sm font-medium h-10 rounded-lg transition-colors border border-gray-200 dark:border-[#3e4552] cursor-pointer">
                 Details
              </button>
            </div>
          </div>
        </aside>

      </div>
    </div>
  );
}
