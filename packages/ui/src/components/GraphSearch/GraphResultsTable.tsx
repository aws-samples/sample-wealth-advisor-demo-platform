import { useMemo } from 'react';
import type { GraphConfig } from './types';
import {
  getDisplayColumns,
  resolveCellValue,
  formatValue,
  downloadTableAsCSV,
  METRIC_LABELS,
  METRIC_TOOLTIPS,
} from '../../hooks/useGraphSearch';
import type { EnrichedSearchResponse, NodeMetrics } from './types';

interface Props {
  config: GraphConfig;
  data: EnrichedSearchResponse;
  searching: boolean;
  onFocusNode: (nodeId: string) => void;
}

export function GraphResultsTable({
  config,
  data,
  searching,
  onFocusNode,
}: Props) {
  // Filter to primary types when available
  const filteredNodes = useMemo(() => {
    let nodes = data.enriched_nodes ?? [];
    if (!nodes.length) return [];
    const typeCounts: Record<string, number> = {};
    nodes.forEach((n) => {
      typeCounts[n.node_type] = (typeCounts[n.node_type] || 0) + 1;
    });
    const hasPrimary = Object.keys(typeCounts).some((t) =>
      config.primaryTypes.has(t),
    );
    if (hasPrimary)
      nodes = nodes.filter((n) => config.primaryTypes.has(n.node_type));
    return nodes;
  }, [data.enriched_nodes, config.primaryTypes]);

  // Compute columns
  const { allColumns, metricColSet } = useMemo(() => {
    if (!filteredNodes.length)
      return { allColumns: [] as string[], metricColSet: new Set<string>() };

    const columns = getDisplayColumns(filteredNodes, config);
    const nodeMetrics = data.node_metrics ?? {};

    const METRIC_SKIP = new Set([
      'connections',
      'property_profile',
      ...config.metricColumns,
    ]);
    const extraMetricKeys = new Set<string>();
    Object.values(nodeMetrics).forEach((m) => {
      Object.keys(m).forEach((k) => {
        if (!METRIC_SKIP.has(k) && typeof m[k] === 'number')
          extraMetricKeys.add(k);
      });
    });
    const metricCols = [...config.metricColumns, ...extraMetricKeys];
    const mcs = new Set(metricCols);

    const all = columns.filter((c) => !config.hiddenColumns.has(c));
    if (!all.includes('connections_summary')) all.push('connections_summary');
    const connIdx = all.indexOf('connections_summary');
    metricCols.forEach((mc) => {
      if (!all.includes(mc)) {
        if (connIdx !== -1) all.splice(connIdx, 0, mc);
        else all.push(mc);
      }
    });

    return { allColumns: all, metricColSet: mcs };
  }, [filteredNodes, config, data.node_metrics]);

  if (searching || !filteredNodes.length) return null;

  const nodeMetrics = data.node_metrics ?? {};
  const explanations = data.column_explanations ?? {};
  const altMetrics = data.alternative_metrics ?? {};
  const hasAltMetrics = Object.keys(altMetrics).length > 0 && altMetrics.reason;
  const hasExplanations = Object.keys(explanations).length > 0;

  return (
    <div className="text-sm">
      {/* Download button */}
      {filteredNodes.length > 0 && (
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-gray-500">
            {filteredNodes.length} result(s)
          </span>
          <button
            className="border border-gray-200 rounded px-2 py-1 text-blue-500 text-xs hover:bg-blue-500 hover:text-white transition-colors cursor-pointer flex items-center gap-1"
            onClick={() =>
              downloadTableAsCSV(
                allColumns,
                filteredNodes,
                nodeMetrics,
                config.virtualColumns,
                config.hiddenColumns,
              )
            }
            title="Download as CSV"
          >
            ⬇ Download CSV
          </button>
        </div>
      )}

      {/* Table */}
      {filteredNodes.length > 0 && allColumns.length > 0 && (
        <div className="mt-1 max-h-[350px] overflow-auto border border-gray-200 rounded-md bg-white">
          <table className="w-full border-collapse text-xs">
            <thead className="sticky top-0 z-[1]">
              <tr>
                {allColumns.map((col) => {
                  const label = METRIC_LABELS[col] || col.replace(/_/g, ' ');
                  const tooltip =
                    explanations[col] ||
                    METRIC_TOOLTIPS[col] ||
                    (col === 'connections_summary'
                      ? "Full breakdown of this node's connections."
                      : '');
                  return (
                    <th
                      key={col}
                      className="bg-gray-100 px-2.5 py-2 text-left font-semibold text-gray-600 uppercase text-[0.7rem] border-b-2 border-gray-200 whitespace-nowrap"
                      title={tooltip}
                    >
                      {label}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {filteredNodes.map((node) => {
                const metrics =
                  nodeMetrics[node.node_id] || ({} as NodeMetrics);
                return (
                  <tr
                    key={node.node_id}
                    className="cursor-pointer hover:bg-blue-50 active:bg-blue-100 transition-colors"
                    onClick={() => onFocusNode(node.node_id)}
                  >
                    {allColumns.map((col) => {
                      let value = resolveCellValue(
                        col,
                        node,
                        metrics,
                        metricColSet,
                        config.virtualColumns,
                      );
                      if (typeof value === 'number')
                        value = formatValue(col, value);
                      const isConn = col === 'connections_summary';
                      return (
                        <td
                          key={col}
                          className={`px-2.5 py-[7px] border-b border-gray-100 text-gray-800 ${
                            isConn
                              ? 'max-w-[350px] whitespace-normal break-words'
                              : 'max-w-[150px] overflow-hidden text-ellipsis whitespace-nowrap'
                          }`}
                          title={String(value)}
                        >
                          {String(value)}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {hasAltMetrics && (
        <p className="mt-1.5 text-[0.7rem] text-orange-500 italic">
          ⚠️ Graph similarity = 0 for all nodes. Showing full connection details
          as alternative context.
        </p>
      )}
      {!hasExplanations && (
        <p className="text-[0.7rem] text-gray-400 italic mt-1">
          ℹ️ Column explanations unavailable
        </p>
      )}
    </div>
  );
}
