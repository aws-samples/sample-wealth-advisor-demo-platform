import { formatValue } from '../../hooks/useGraphSearch';

interface NodeData {
  id: string;
  label: string;
  color: string;
  nodeType: string;
  properties: Record<string, unknown>;
}

interface Props {
  node: NodeData | null;
  connectedNodes: NodeData[];
  onClose: () => void;
  onSelectNode: (id: string) => void;
}

export function GraphDetailPanel({
  node,
  connectedNodes,
  onClose,
  onSelectNode,
}: Props) {
  if (!node) return null;

  return (
    <aside className="h-full bg-white border-l border-slate-200 flex flex-col overflow-y-auto">
      {/* Header */}
      <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
        <div className="flex items-center gap-2.5 min-w-0">
          <span
            className="w-3 h-3 rounded-full flex-shrink-0"
            style={{ backgroundColor: node.color }}
          />
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider truncate">
            {node.nodeType}
          </span>
        </div>
        <button
          onClick={onClose}
          className="w-7 h-7 flex items-center justify-center rounded-md hover:bg-slate-100 text-slate-400 transition-colors flex-shrink-0"
          aria-label="Close detail panel"
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 14 14"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          >
            <path d="M3 3l8 8M11 3l-8 8" />
          </svg>
        </button>
      </div>

      <div className="p-5">
        <h3 className="text-base font-semibold text-slate-800 leading-snug">
          {node.label}
        </h3>

        {/* Properties */}
        <div className="mt-4 space-y-0">
          {Object.entries(node.properties || {}).map(([k, v]) => (
            <div
              key={k}
              className="py-2.5 border-b border-slate-50 last:border-0"
            >
              <div className="text-[0.65rem] text-slate-400 uppercase tracking-wider">
                {k.replace(/_/g, ' ')}
              </div>
              <div className="text-sm text-slate-700 mt-0.5">
                {formatValue(k, v)}
              </div>
            </div>
          ))}
        </div>

        {/* Connected nodes */}
        {connectedNodes.length > 0 && (
          <div className="mt-5 pt-4 border-t border-slate-100">
            <h4 className="text-[0.65rem] text-slate-400 font-semibold uppercase tracking-wider mb-2">
              Connections ({connectedNodes.length})
            </h4>
            <div className="space-y-0.5">
              {connectedNodes.map((n) => (
                <button
                  key={n.id}
                  className="w-full flex items-center py-2 px-2 rounded-md hover:bg-slate-50 cursor-pointer transition-colors text-left"
                  onClick={() => onSelectNode(n.id)}
                >
                  <span
                    className="w-2 h-2 rounded-full mr-2.5 flex-shrink-0"
                    style={{ backgroundColor: n.color }}
                  />
                  <span className="text-sm text-slate-600 truncate flex-1">
                    {n.label}
                  </span>
                  <span className="text-[0.65rem] text-slate-400 ml-2">
                    {n.nodeType}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
