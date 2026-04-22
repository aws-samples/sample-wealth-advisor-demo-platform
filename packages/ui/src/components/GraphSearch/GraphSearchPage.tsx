import { useEffect, useMemo, useState } from 'react';
import { useGraphSearch } from '../../hooks/useGraphSearch';
import { GraphSearchSidebar } from './GraphSearchSidebar';
import { GraphCanvas } from './GraphCanvas';
import { GraphDetailPanel } from './GraphDetailPanel';
import { Spinner } from '../spinner';

export function GraphSearchPage() {
  const {
    config,
    loading,
    loadingMessage,
    searching,
    searchStatus,
    status,
    searchResults,
    streamingReasoning,
    selectedNodeId,
    setSelectedNodeId,
    filters,
    toggleFilter,
    containerRef,
    loadGraph,
    loadData,
    search,
    zoomIn,
    zoomOut,
    fitView,
    focusNode,
    getNodeData,
    getConnectedNodes,
  } = useGraphSearch();

  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);

  useEffect(() => {
    if (!config) return;
    const check = setInterval(async () => {
      if ((window as any).vis && containerRef.current) {
        clearInterval(check);
        await loadGraph();
      }
    }, 200);
    return () => clearInterval(check);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config]);

  const selectedNode = useMemo(
    () => (selectedNodeId ? getNodeData(selectedNodeId) : null),
    [selectedNodeId, getNodeData],
  );

  const connectedNodes = useMemo(
    () => (selectedNodeId ? getConnectedNodes(selectedNodeId) : []),
    [selectedNodeId, getConnectedNodes],
  );

  // Auto-open right panel when a node is selected
  useEffect(() => {
    if (selectedNode) setRightOpen(true);
  }, [selectedNode]);

  if (!config) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-slate-50">
        <Spinner />
        <p className="mt-3 text-slate-400 text-sm">Loading graph data…</p>
      </div>
    );
  }

  return (
    <div className="relative flex h-full overflow-hidden bg-slate-50">
      {/* Left panel toggle (visible when collapsed) */}
      {!leftOpen && (
        <button
          onClick={() => setLeftOpen(true)}
          className="absolute top-3 left-3 z-30 w-9 h-9 flex items-center justify-center rounded-lg bg-white border border-slate-200 shadow-sm hover:bg-slate-50 text-slate-500 transition-colors"
          title="Open sidebar"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          >
            <path d="M4 2v12M7 5l3 3-3 3" />
          </svg>
        </button>
      )}

      {/* Left sidebar */}
      <div
        className={`relative flex-shrink-0 transition-all duration-300 ease-in-out ${leftOpen ? 'w-[380px]' : 'w-0'} overflow-hidden`}
      >
        <div className="w-[380px] h-full">
          <GraphSearchSidebar
            config={config}
            filters={filters}
            status={status}
            searching={searching}
            searchStatus={searchStatus}
            searchResults={searchResults}
            streamingReasoning={streamingReasoning}
            onToggleFilter={toggleFilter}
            onSearch={search}
            onFocusNode={focusNode}
            onLoadData={loadData}
            onRefresh={async () => {
              await loadGraph();
            }}
            onCollapse={() => setLeftOpen(false)}
          />
        </div>
      </div>

      {/* Center: graph canvas */}
      <div className="flex-1 flex flex-col min-w-0 relative">
        <GraphCanvas
          containerRef={containerRef}
          loading={loading}
          loadingMessage={loadingMessage}
          onZoomIn={zoomIn}
          onZoomOut={zoomOut}
          onFitView={fitView}
        />
      </div>

      {/* Right detail panel */}
      <div
        className={`relative flex-shrink-0 transition-all duration-300 ease-in-out ${rightOpen && selectedNode ? 'w-[320px]' : 'w-0'} overflow-hidden`}
      >
        <div className="w-[320px] h-full">
          <GraphDetailPanel
            node={selectedNode}
            connectedNodes={connectedNodes}
            onClose={() => {
              setSelectedNodeId(null);
              setRightOpen(false);
            }}
            onSelectNode={focusNode}
          />
        </div>
      </div>
    </div>
  );
}
