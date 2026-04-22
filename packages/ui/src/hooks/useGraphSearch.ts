import { useState, useRef, useCallback, useEffect } from 'react';
import type {
  GraphConfig,
  ServerConfig,
  EnrichedSearchResponse,
  EnrichedNode,
  NodeMetrics,
  VirtualColumnDef,
} from '../components/GraphSearch/types';
import {
  fetchGraphConfig,
  fetchGraphData,
  loadDataToNeptune as apiLoadData,
  enrichedSearchStream,
  setGraphSearchBaseUrl,
  setGraphSearchAuth,
  setGraphSearchAgent,
} from '../services/graph-service';
import { useRuntimeConfig } from './useRuntimeConfig';
import { useAuth } from 'react-oidc-context';

// ── Fallback config (used when /api/config is unreachable) ──────────────────

const FALLBACK: ServerConfig = {
  default_node_limit: 5000,
  node_types: {
    Advisor: { color: '#4A90D9', icon: '\uf508', size: 75, primary: true },
    Client: { color: '#7CB342', icon: '\uf007', size: 40, primary: true },
    Company: { color: '#FF9800', icon: '\uf1ad', size: 40, primary: false },
    City: { color: '#9C27B0', icon: '\uf015', size: 40, primary: false },
    Stock: { color: '#F44336', icon: '\uf201', size: 40, primary: false },
    RiskProfile: { color: '#009688', icon: '\uf3ed', size: 40, primary: false },
  },
  column_strategy: {
    Client: [
      'name',
      'portfolio_value',
      'net_worth',
      'job_title',
      'return_ytd',
      'holdings',
      'connections_summary',
    ],
    Advisor: ['name', 'clients', 'connections_summary'],
    Company: ['name', 'connections_summary'],
    Stock: ['name', 'connections_summary'],
    City: ['name', 'state', 'connections_summary'],
    RiskProfile: ['level', 'connections_summary'],
  },
  virtual_columns: {
    holdings: {
      source: 'related_nodes',
      filter_type: 'Stock',
      filter_rel: 'HOLDS',
    },
    clients: {
      source: 'related_nodes',
      filter_type: 'Client',
      filter_rel: 'MANAGES',
    },
  },
  label_properties: [
    'first_name+last_name',
    'name',
    'ticker',
    'level',
    'label',
  ],
  metric_columns: [
    'degree_centrality',
    'jaccard_avg',
    'overlap_avg',
    'common_neighbors_avg',
  ],
  hidden_columns: ['type', 'first_name', 'last_name'],
  examples: [
    'Client Segmentation: Which clients cluster together by investment style based on shared stock holdings?',
    'Client Segmentation: Segment clients interested in the healthcare sector',
    "Cross-sell / Upsell: Recommend stocks to Brian Green based on what similar investors hold that he doesn't",
    'Cross-sell / Upsell: Which clients are most similar to Steven Reed based on invested stocks',
    'Cross-sell / Upsell: Find stocks that frequently appear together in portfolios?',
    'Advisor Optimization: Find advisors whose clients span the most diverse geographic regions for expansion planning',
    'Risk Exposure: Which clients are most exposed if the defense sector drops',
  ],
};

// ── Helpers ─────────────────────────────────────────────────────────────────

export type { GraphConfig } from '../components/GraphSearch/types';

function buildConfig(src: ServerConfig): GraphConfig {
  const cfg: GraphConfig = {
    nodeLimit: src.default_node_limit ?? 5000,
    colors: {},
    icons: {},
    sizes: {},
    primaryTypes: new Set<string>(),
    columnStrategy: src.column_strategy ?? {},
    virtualColumns: src.virtual_columns ?? {},
    labelProperties: src.label_properties ?? [],
    metricColumns: src.metric_columns ?? [],
    hiddenColumns: new Set(src.hidden_columns ?? []),
    examples: src.examples ?? [],
  };
  if (src.node_types) {
    for (const [type, def] of Object.entries(src.node_types)) {
      cfg.colors[type] = def.color;
      cfg.icons[type] = def.icon;
      cfg.sizes[type] = def.size || 40;
      if (def.primary) cfg.primaryTypes.add(type);
    }
  }
  return cfg;
}

export function resolveDisplayLabel(
  props: Record<string, unknown>,
  labelProperties: string[],
  fallbackId: string,
): string {
  for (const rule of labelProperties) {
    if (rule.includes('+')) {
      const parts = rule
        .split('+')
        .map((k) => String(props[k] ?? '').trim())
        .filter(Boolean);
      if (parts.length > 0) return parts.join(' ');
    } else if (props[rule]) {
      return String(props[rule]);
    }
  }
  return fallbackId;
}

export function formatValue(key: string, value: unknown): string {
  if (
    typeof value === 'number' &&
    (key.includes('value') || key.includes('worth'))
  ) {
    return '$' + value.toLocaleString();
  }
  return String(value ?? '');
}

export function buildConnectionsSummary(
  metrics: NodeMetrics | undefined,
  relatedNodes: EnrichedNode['related_nodes'],
): string {
  const conns = metrics?.connections ?? {};
  if (Object.keys(conns).length > 0) {
    return Object.entries(conns)
      .map(
        ([rel, items]) =>
          `${rel}: ${Array.isArray(items) ? items.join(', ') : String(items)}`,
      )
      .join(' | ');
  }
  if (relatedNodes && relatedNodes.length > 0) {
    const grouped: Record<string, string[]> = {};
    for (const rn of relatedNodes) {
      const key = (rn.relationship_type || 'Related')
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (c) => c.toUpperCase());
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(rn.node_label);
    }
    return Object.entries(grouped)
      .map(([rel, names]) => `${rel}: ${names.join(', ')}`)
      .join(' | ');
  }
  return '';
}

export function resolveCellValue(
  col: string,
  node: EnrichedNode,
  metrics: NodeMetrics,
  metricColSet: Set<string>,
  virtualColumns: Record<string, VirtualColumnDef>,
): string | number {
  if (col === 'name') return node.node_label || '';
  const vc = virtualColumns[col];
  if (vc && node.related_nodes) {
    return node.related_nodes
      .filter(
        (r) =>
          r.node_type === vc.filter_type ||
          r.relationship_type === vc.filter_rel,
      )
      .map((r) => r.node_label)
      .join(', ');
  }
  if (col === 'connections_summary')
    return buildConnectionsSummary(metrics, node.related_nodes);
  // Node properties take priority over metrics (only primitives)
  const propVal = node.properties[col];
  if (propVal !== undefined && propVal !== null && typeof propVal !== 'object')
    return propVal as string | number;
  if (metricColSet.has(col)) {
    const v = metrics[col];
    if (v !== undefined && v !== null) {
      return typeof v === 'number'
        ? Number.isInteger(v)
          ? v
          : Number(v.toFixed(4))
        : String(v);
    }
    return '—';
  }
  return '';
}

export function getDisplayColumns(
  enrichedNodes: EnrichedNode[],
  config: GraphConfig,
): string[] {
  if (!enrichedNodes.length) return ['name', 'connections_summary'];

  const typeCounts: Record<string, number> = {};
  for (const n of enrichedNodes) {
    const t = n.node_type || 'Unknown';
    typeCounts[t] = (typeCounts[t] || 0) + 1;
  }

  const types = Object.keys(typeCounts);
  const predominantType = types.reduce((a, b) =>
    typeCounts[a] >= typeCounts[b] ? a : b,
  );
  const isMixed =
    types.length > 1 &&
    typeCounts[predominantType] / enrichedNodes.length <= 0.5;

  if (isMixed || !config.columnStrategy[predominantType]) {
    const propCounts: Record<string, number> = {};
    for (const n of enrichedNodes) {
      for (const k of Object.keys(n.properties || {})) {
        if (!config.hiddenColumns.has(k) && k !== 'name') {
          propCounts[k] = (propCounts[k] || 0) + 1;
        }
      }
    }
    const topProps = Object.entries(propCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([k]) => k);
    return ['name', ...topProps, 'connections_summary'];
  }

  const cols = config.columnStrategy[predominantType].filter(
    (c) => !config.hiddenColumns.has(c),
  );
  if (!cols.includes('name')) cols.unshift('name');
  if (!cols.includes('connections_summary')) cols.push('connections_summary');
  return cols;
}

// ── CSV download ────────────────────────────────────────────────────────────

export const METRIC_LABELS: Record<string, string> = {
  degree_centrality: 'Degree Centrality',
  jaccard_avg: 'Jaccard Similarity',
  overlap_avg: 'Overlap Similarity',
  common_neighbors_avg: 'Common Neighbors',
  connections_summary: 'Connections Summary',
};

export const METRIC_TOOLTIPS: Record<string, string> = {
  score:
    'Similarity score from the graph algorithm (Jaccard or Overlap). 0 = no shared neighbors, 1 = identical neighborhoods.',
  common: 'Number of common neighbors shared between two nodes in the graph.',
  total: 'Total unique neighbors across both nodes combined.',
  degree_centrality:
    'Total number of direct connections (edges) this node has.',
  jaccard_avg:
    'Average pairwise Jaccard similarity across matched nodes (0–1).',
  common_neighbors_avg:
    'Average count of common neighbors across matched nodes.',
  overlap_avg:
    'Average pairwise Overlap similarity across matched nodes (0–1).',
};

export function downloadTableAsCSV(
  columns: string[],
  nodes: EnrichedNode[],
  nodeMetrics: Record<string, NodeMetrics>,
  virtualColumns: Record<string, VirtualColumnDef>,
  hiddenColumns: Set<string>,
) {
  const csvEscape = (val: unknown) => {
    const s = String(val ?? '');
    return s.includes(',') || s.includes('"') || s.includes('\n')
      ? '"' + s.replace(/"/g, '""') + '"'
      : s;
  };

  const vcKeys = new Set(Object.keys(virtualColumns));
  const metricColSet = new Set(
    columns.filter(
      (c) =>
        c !== 'name' &&
        c !== 'connections_summary' &&
        !vcKeys.has(c) &&
        !hiddenColumns.has(c),
    ),
  );

  const header = columns
    .map((c) => csvEscape(METRIC_LABELS[c] || c.replace(/_/g, ' ')))
    .join(',');
  const rows = nodes.map((node) => {
    const metrics = nodeMetrics[node.node_id] || ({} as NodeMetrics);
    return columns
      .map((col) =>
        csvEscape(
          resolveCellValue(col, node, metrics, metricColSet, virtualColumns),
        ),
      )
      .join(',');
  });

  const csv = '\uFEFF' + [header, ...rows].join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `graph_search_results_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Demo / dummy data ───────────────────────────────────────────────────────

function getDemoGraphData() {
  const nodes = [
    {
      id: 'adv-1',
      label: 'Jane Smith',
      type: 'Advisor',
      properties: { first_name: 'Jane', last_name: 'Smith', advisor_id: 1 },
    },
    {
      id: 'adv-2',
      label: 'Michael Johnson',
      type: 'Advisor',
      properties: {
        first_name: 'Michael',
        last_name: 'Johnson',
        advisor_id: 2,
      },
    },
    {
      id: 'cli-1',
      label: 'Steven Reed',
      type: 'Client',
      properties: {
        first_name: 'Steven',
        last_name: 'Reed',
        client_id: 101,
        portfolio_value: 4200000,
        net_worth: 8500000,
        job_title: 'CEO',
        return_ytd: 12.5,
      },
    },
    {
      id: 'cli-2',
      label: 'Emily Chen',
      type: 'Client',
      properties: {
        first_name: 'Emily',
        last_name: 'Chen',
        client_id: 102,
        portfolio_value: 2800000,
        net_worth: 5200000,
        job_title: 'CFO',
        return_ytd: 8.3,
      },
    },
    {
      id: 'cli-3',
      label: 'Robert Williams',
      type: 'Client',
      properties: {
        first_name: 'Robert',
        last_name: 'Williams',
        client_id: 103,
        portfolio_value: 6100000,
        net_worth: 12000000,
        job_title: 'Founder',
        return_ytd: 15.7,
      },
    },
    {
      id: 'cli-4',
      label: 'Sarah Davis',
      type: 'Client',
      properties: {
        first_name: 'Sarah',
        last_name: 'Davis',
        client_id: 104,
        portfolio_value: 1500000,
        net_worth: 3100000,
        job_title: 'VP Engineering',
        return_ytd: -2.1,
      },
    },
    {
      id: 'cli-5',
      label: 'James Wilson',
      type: 'Client',
      properties: {
        first_name: 'James',
        last_name: 'Wilson',
        client_id: 105,
        portfolio_value: 3400000,
        net_worth: 7800000,
        job_title: 'Managing Director',
        return_ytd: 9.8,
      },
    },
    {
      id: 'cli-6',
      label: 'Lisa Park',
      type: 'Client',
      properties: {
        first_name: 'Lisa',
        last_name: 'Park',
        client_id: 106,
        portfolio_value: 5500000,
        net_worth: 11000000,
        job_title: 'Partner',
        return_ytd: 11.2,
      },
    },
    {
      id: 'stk-1',
      label: 'AAPL',
      type: 'Stock',
      properties: { ticker: 'AAPL', name: 'Apple Inc.' },
    },
    {
      id: 'stk-2',
      label: 'MSFT',
      type: 'Stock',
      properties: { ticker: 'MSFT', name: 'Microsoft Corp.' },
    },
    {
      id: 'stk-3',
      label: 'GOOGL',
      type: 'Stock',
      properties: { ticker: 'GOOGL', name: 'Alphabet Inc.' },
    },
    {
      id: 'stk-4',
      label: 'AMZN',
      type: 'Stock',
      properties: { ticker: 'AMZN', name: 'Amazon.com Inc.' },
    },
    {
      id: 'stk-5',
      label: 'NVDA',
      type: 'Stock',
      properties: { ticker: 'NVDA', name: 'NVIDIA Corp.' },
    },
    {
      id: 'cmp-1',
      label: 'Goldman Sachs',
      type: 'Company',
      properties: { name: 'Goldman Sachs' },
    },
    {
      id: 'cmp-2',
      label: 'JP Morgan',
      type: 'Company',
      properties: { name: 'JP Morgan Chase' },
    },
    {
      id: 'cty-1',
      label: 'New York',
      type: 'City',
      properties: { name: 'New York', state: 'NY' },
    },
    {
      id: 'cty-2',
      label: 'San Francisco',
      type: 'City',
      properties: { name: 'San Francisco', state: 'CA' },
    },
    {
      id: 'cty-3',
      label: 'Seattle',
      type: 'City',
      properties: { name: 'Seattle', state: 'WA' },
    },
    {
      id: 'rsk-1',
      label: 'Aggressive',
      type: 'RiskProfile',
      properties: { level: 'Aggressive' },
    },
    {
      id: 'rsk-2',
      label: 'Moderate',
      type: 'RiskProfile',
      properties: { level: 'Moderate' },
    },
    {
      id: 'rsk-3',
      label: 'Conservative',
      type: 'RiskProfile',
      properties: { level: 'Conservative' },
    },
  ];

  const edges = [
    // Advisor -> Client (MANAGES)
    { source_id: 'adv-1', target_id: 'cli-1', type: 'MANAGES' },
    { source_id: 'adv-1', target_id: 'cli-2', type: 'MANAGES' },
    { source_id: 'adv-1', target_id: 'cli-3', type: 'MANAGES' },
    { source_id: 'adv-2', target_id: 'cli-4', type: 'MANAGES' },
    { source_id: 'adv-2', target_id: 'cli-5', type: 'MANAGES' },
    { source_id: 'adv-2', target_id: 'cli-6', type: 'MANAGES' },
    // Client -> Stock (HOLDS)
    { source_id: 'cli-1', target_id: 'stk-1', type: 'HOLDS' },
    { source_id: 'cli-1', target_id: 'stk-2', type: 'HOLDS' },
    { source_id: 'cli-1', target_id: 'stk-5', type: 'HOLDS' },
    { source_id: 'cli-2', target_id: 'stk-1', type: 'HOLDS' },
    { source_id: 'cli-2', target_id: 'stk-3', type: 'HOLDS' },
    { source_id: 'cli-3', target_id: 'stk-2', type: 'HOLDS' },
    { source_id: 'cli-3', target_id: 'stk-4', type: 'HOLDS' },
    { source_id: 'cli-3', target_id: 'stk-5', type: 'HOLDS' },
    { source_id: 'cli-4', target_id: 'stk-3', type: 'HOLDS' },
    { source_id: 'cli-4', target_id: 'stk-4', type: 'HOLDS' },
    { source_id: 'cli-5', target_id: 'stk-1', type: 'HOLDS' },
    { source_id: 'cli-5', target_id: 'stk-2', type: 'HOLDS' },
    { source_id: 'cli-5', target_id: 'stk-4', type: 'HOLDS' },
    { source_id: 'cli-6', target_id: 'stk-3', type: 'HOLDS' },
    { source_id: 'cli-6', target_id: 'stk-5', type: 'HOLDS' },
    // Client -> Company (WORKS_AT)
    { source_id: 'cli-1', target_id: 'cmp-1', type: 'WORKS_AT' },
    { source_id: 'cli-2', target_id: 'cmp-2', type: 'WORKS_AT' },
    { source_id: 'cli-5', target_id: 'cmp-1', type: 'WORKS_AT' },
    // Client -> City (LIVES_IN)
    { source_id: 'cli-1', target_id: 'cty-1', type: 'LIVES_IN' },
    { source_id: 'cli-2', target_id: 'cty-2', type: 'LIVES_IN' },
    { source_id: 'cli-3', target_id: 'cty-2', type: 'LIVES_IN' },
    { source_id: 'cli-4', target_id: 'cty-3', type: 'LIVES_IN' },
    { source_id: 'cli-5', target_id: 'cty-1', type: 'LIVES_IN' },
    { source_id: 'cli-6', target_id: 'cty-3', type: 'LIVES_IN' },
    // Client -> RiskProfile (HAS_RISK)
    { source_id: 'cli-1', target_id: 'rsk-1', type: 'HAS_RISK' },
    { source_id: 'cli-2', target_id: 'rsk-2', type: 'HAS_RISK' },
    { source_id: 'cli-3', target_id: 'rsk-1', type: 'HAS_RISK' },
    { source_id: 'cli-4', target_id: 'rsk-3', type: 'HAS_RISK' },
    { source_id: 'cli-5', target_id: 'rsk-2', type: 'HAS_RISK' },
    { source_id: 'cli-6', target_id: 'rsk-1', type: 'HAS_RISK' },
  ];

  return { nodes, edges };
}

// ── Main hook ───────────────────────────────────────────────────────────────

export type GraphStatus = { message: string; type: 'ok' | 'warn' | 'err' | '' };

export function useGraphSearch() {
  const { graphSearchApiUrl, graphSearchAgentArn, cognitoProps } =
    useRuntimeConfig();
  const auth = useAuth();
  const [config, setConfig] = useState<GraphConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMessage, setLoadingMessage] = useState('Loading graph data...');
  const [searching, setSearching] = useState(false);
  const [searchStatus, setSearchStatus] = useState('');
  const [status, setStatus] = useState<GraphStatus>({ message: '', type: '' });
  const [searchResults, setSearchResults] =
    useState<EnrichedSearchResponse | null>(null);
  const [streamingReasoning, setStreamingReasoning] = useState('');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [filters, setFilters] = useState<Record<string, boolean>>({});

  // vis.js refs (managed imperatively)
  const networkRef = useRef<any>(null);
  const nodesDSRef = useRef<any>(null);
  const edgesDSRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // ── Init config ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (graphSearchApiUrl) setGraphSearchBaseUrl(graphSearchApiUrl);
    setGraphSearchAuth(() => auth.user?.id_token);
    if (graphSearchAgentArn && cognitoProps) {
      setGraphSearchAgent(
        graphSearchAgentArn,
        cognitoProps.region,
        cognitoProps.identityPoolId,
        cognitoProps.userPoolId,
      );
    }
    (async () => {
      let serverCfg: ServerConfig | null = null;
      try {
        serverCfg = await fetchGraphConfig();
      } catch {
        console.warn('Could not fetch /api/config, using fallback');
      }
      const cfg = buildConfig(serverCfg || FALLBACK);
      setConfig(cfg);
      // Init filter state from node types
      const f: Record<string, boolean> = {};
      for (const type of Object.keys(cfg.colors)) f[type] = true;
      setFilters(f);
    })();
  }, [
    graphSearchApiUrl,
    graphSearchAgentArn,
    cognitoProps,
    auth.user?.id_token,
  ]);

  // ── Build graph data payload from current DataSets ──────────────────────
  const buildGraphPayload = useCallback(() => {
    const nodes: {
      id: string;
      label: string;
      type: string;
      properties: Record<string, unknown>;
    }[] = [];
    const edges: { source: string; target: string; label: string }[] = [];
    nodesDSRef.current?.forEach((n: any) => {
      nodes.push({
        id: n.id,
        label: n.label,
        type: n.nodeType || '',
        properties: n.properties || {},
      });
    });
    edgesDSRef.current?.forEach((e: any) => {
      edges.push({ source: e.from, target: e.to, label: e.label || '' });
    });
    return { nodes, edges };
  }, []);

  // ── Load graph from Neptune ─────────────────────────────────────────────
  const loadGraph = useCallback(async () => {
    if (!config) return false;
    setLoading(true);
    setLoadingMessage('Loading graph data...');
    setStatus({ message: 'Fetching from Neptune...', type: '' });
    try {
      const data = await fetchGraphData(config.nodeLimit);
      if (!data.nodes?.length) {
        throw new Error('No data returned');
      }
      setLoadingMessage(`Rendering ${data.nodes.length} nodes...`);
      initNetwork(data.nodes, data.edges, config);
      setStatus({
        message: `✅ ${data.nodes.length} nodes, ${data.edges.length} edges`,
        type: 'ok',
      });
      return true;
    } catch {
      console.warn('Neptune API unavailable, loading demo data');
      const demo = getDemoGraphData();
      setLoadingMessage(`Rendering ${demo.nodes.length} nodes...`);
      initNetwork(demo.nodes, demo.edges, config);
      setStatus({
        message: '⚠️ Demo mode — Neptune API unavailable',
        type: 'warn',
      });
      return true;
    }
  }, [config]);

  // ── Init vis.js network ─────────────────────────────────────────────────
  const initNetwork = useCallback(
    (rawNodes: any[], rawEdges: any[], cfg: GraphConfig) => {
      if (!containerRef.current || !(window as any).vis) return;
      const vis = (window as any).vis;

      const nodes = rawNodes.map((n: any) => {
        const hasType = n.type !== undefined;
        const nodeType = hasType ? n.type : n.label;
        const props = n.properties || {};
        const displayLabel = hasType
          ? n.label
          : resolveDisplayLabel(props, cfg.labelProperties, n.id);
        const color = cfg.colors[nodeType] || '#999';
        const nodeSize = cfg.sizes[nodeType] || 40;
        const base: any = {
          id: n.id,
          label: displayLabel,
          color,
          title: `${nodeType}: ${displayLabel}`,
          nodeType,
          properties: props,
          size: nodeSize,
        };
        if (cfg.icons[nodeType]) {
          base.shape = 'icon';
          base.icon = {
            face: 'FontAwesome',
            code: cfg.icons[nodeType],
            size: Math.max(nodeSize, 50),
            color,
          };
        }
        return base;
      });

      const edges = rawEdges.map((e: any, i: number) => ({
        id: `e${i}`,
        from: e.source_id || e.source,
        to: e.target_id || e.target,
        label: e.type || e.label,
        arrows: 'to',
        font: { size: 10 },
      }));

      const nodesDS = new vis.DataSet(nodes);
      const edgesDS = new vis.DataSet(edges);
      nodesDSRef.current = nodesDS;
      edgesDSRef.current = edgesDS;

      if (networkRef.current) networkRef.current.destroy();

      const network = new vis.Network(
        containerRef.current,
        { nodes: nodesDS, edges: edgesDS },
        {
          nodes: { shape: 'dot', size: 20, font: { size: 12 }, borderWidth: 2 },
          edges: {
            width: 1,
            color: '#848484',
            font: { size: 9, color: '#666' },
          },
          physics: {
            solver: 'forceAtlas2Based',
            forceAtlas2Based: {
              gravitationalConstant: -50,
              centralGravity: 0.01,
              springLength: 100,
            },
          },
          interaction: { hover: true, tooltipDelay: 200 },
        },
      );

      network.on('click', (params: any) => {
        resetEdges();
        if (params.nodes.length) {
          setSelectedNodeId(params.nodes[0]);
          highlightEdges([params.nodes[0]]);
        }
      });
      network.on('hoverNode', (e: any) => setSelectedNodeId(e.node));

      network.once('stabilizationIterationsDone', () => {
        setLoading(false);
      });
      // Fallback: hide loading after 10s even if stabilization hasn't finished
      setTimeout(() => setLoading(false), 10000);

      networkRef.current = network;
    },
    [],
  );

  // ── Edge helpers ────────────────────────────────────────────────────────
  const resetEdges = useCallback(() => {
    const ds = edgesDSRef.current;
    if (!ds) return;
    const updates: any[] = [];
    ds.forEach((e: any) =>
      updates.push({ id: e.id, color: '#848484', width: 1 }),
    );
    ds.update(updates);
  }, []);

  const highlightEdges = useCallback((nodeIds: string[]) => {
    const ds = edgesDSRef.current;
    if (!ds) return;
    const idSet = new Set(nodeIds);
    const updates: any[] = [];
    ds.forEach((e: any) => {
      if (idSet.has(e.from) || idSet.has(e.to)) {
        updates.push({ id: e.id, color: '#FF9800', width: 3 });
      }
    });
    if (updates.length) ds.update(updates);
  }, []);

  // ── Filter toggle ───────────────────────────────────────────────────────
  const toggleFilter = useCallback((type: string) => {
    setFilters((prev) => {
      const next = { ...prev, [type]: !prev[type] };
      // Apply to vis DataSet
      if (nodesDSRef.current) {
        const updates: any[] = [];
        nodesDSRef.current.forEach((n: any) =>
          updates.push({ id: n.id, hidden: !next[n.nodeType] }),
        );
        nodesDSRef.current.update(updates);
      }
      return next;
    });
  }, []);

  // ── Load data to Neptune ────────────────────────────────────────────────
  const loadData = useCallback(async () => {
    setStatus({ message: 'Loading data to Neptune...', type: '' });
    try {
      await apiLoadData();
      setStatus({ message: '✅ Data loaded, refreshing...', type: 'ok' });
      await loadGraph();
    } catch (e: any) {
      setStatus({ message: `❌ ${e.message}`, type: 'err' });
    }
  }, [loadGraph]);

  // ── AI search ───────────────────────────────────────────────────────────
  const search = useCallback(
    async (query: string) => {
      if (!query.trim()) return;
      setSearching(true);
      setSearchResults(null);
      setStreamingReasoning('');
      setSearchStatus('Initializing search...');
      resetEdges();
      networkRef.current?.unselectAll();

      try {
        const graphPayload = buildGraphPayload();
        let matchHandled = false;
        const data = await enrichedSearchStream(
          query,
          graphPayload,
          (msg) => setSearchStatus(msg),
          (token) => setStreamingReasoning((prev) => prev + token),
          (matchingIds) => {
            if (matchingIds?.length && networkRef.current) {
              networkRef.current.selectNodes(matchingIds);
              networkRef.current.focus(matchingIds[0], {
                scale: 1.2,
                animation: true,
              });
              highlightEdges(matchingIds);
              matchHandled = true;
            }
          },
        );
        setStreamingReasoning('');
        setSearchResults(data);
        setSearchStatus('');

        if (!matchHandled && data.matching_ids?.length && networkRef.current) {
          networkRef.current.selectNodes(data.matching_ids);
          networkRef.current.focus(data.matching_ids[0], {
            scale: 1.2,
            animation: true,
          });
          highlightEdges(data.matching_ids);
        }
      } catch (e: any) {
        setSearchStatus('');
        setSearchResults({
          matching_ids: [],
          explanation: e.message,
        } as EnrichedSearchResponse);
      } finally {
        setSearching(false);
      }
    },
    [buildGraphPayload, resetEdges, highlightEdges],
  );

  // ── View controls ───────────────────────────────────────────────────────
  const zoomIn = useCallback(() => {
    networkRef.current?.moveTo({
      scale: networkRef.current.getScale() * 1.3,
      animation: true,
    });
  }, []);
  const zoomOut = useCallback(() => {
    networkRef.current?.moveTo({
      scale: networkRef.current.getScale() / 1.3,
      animation: true,
    });
  }, []);
  const fitView = useCallback(() => {
    networkRef.current?.fit({ animation: true });
  }, []);

  // ── Focus a specific node (from table row click) ────────────────────────
  const focusNode = useCallback(
    (nodeId: string) => {
      if (!networkRef.current || !nodesDSRef.current) return;
      networkRef.current.focus(nodeId, { scale: 1.5, animation: true });
      networkRef.current.selectNodes([nodeId]);
      resetEdges();
      highlightEdges([nodeId]);
      setSelectedNodeId(nodeId);
    },
    [resetEdges, highlightEdges],
  );

  // ── Get node data for detail panel ──────────────────────────────────────
  const getNodeData = useCallback((nodeId: string) => {
    return nodesDSRef.current?.get(nodeId) ?? null;
  }, []);

  const getConnectedNodes = useCallback((nodeId: string) => {
    if (!networkRef.current || !nodesDSRef.current) return [];
    return networkRef.current
      .getConnectedNodes(nodeId)
      .map((id: string) => nodesDSRef.current.get(id))
      .filter(Boolean);
  }, []);

  return {
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
  };
}
