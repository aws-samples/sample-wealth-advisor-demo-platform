// ── Graph Search Types ──────────────────────────────────────────────────────

/** Raw node from Neptune API */
export interface GraphNode {
  id: string;
  label: string;
  type: string;
  properties: Record<string, unknown>;
}

/** Raw edge from Neptune API */
export interface GraphEdge {
  source_id?: string;
  source?: string;
  target_id?: string;
  target?: string;
  type?: string;
  label?: string;
}

/** Graph data response from /api/graph */
export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

/** Node type definition from /api/config */
export interface NodeTypeDef {
  color: string;
  icon: string;
  size: number;
  primary: boolean;
}

/** Virtual column definition */
export interface VirtualColumnDef {
  source: string;
  filter_type: string;
  filter_rel: string;
}

/** Server config from /api/config */
export interface ServerConfig {
  default_node_limit?: number;
  node_types?: Record<string, NodeTypeDef>;
  column_strategy?: Record<string, string[]>;
  virtual_columns?: Record<string, VirtualColumnDef>;
  label_properties?: string[];
  metric_columns?: string[];
  hidden_columns?: string[];
  examples?: string[];
}

/** Resolved app-level config (after merging server + fallback) */
export interface GraphConfig {
  nodeLimit: number;
  colors: Record<string, string>;
  icons: Record<string, string>;
  sizes: Record<string, number>;
  primaryTypes: Set<string>;
  columnStrategy: Record<string, string[]>;
  virtualColumns: Record<string, VirtualColumnDef>;
  labelProperties: string[];
  metricColumns: string[];
  hiddenColumns: Set<string>;
  examples: string[];
}

/** Related node in enriched response */
export interface RelatedNode {
  node_id: string;
  node_label: string;
  node_type: string;
  relationship_type: string;
}

/** Enriched node from AI search */
export interface EnrichedNode {
  node_id: string;
  node_label: string;
  node_type: string;
  properties: Record<string, unknown>;
  related_nodes?: RelatedNode[];
}

/** Node metrics from AI search */
export interface NodeMetrics {
  connections?: Record<string, string[] | string>;
  degree_centrality?: number;
  jaccard_avg?: number;
  overlap_avg?: number;
  common_neighbors_avg?: number;
  [key: string]: unknown;
}

/** Enriched search response from /api/nl-search-enriched */
export interface EnrichedSearchResponse {
  matching_ids: string[];
  reasoning?: string;
  explanation?: string;
  enriched_nodes?: EnrichedNode[];
  column_explanations?: Record<string, string>;
  node_metrics?: Record<string, NodeMetrics>;
  alternative_metrics?: { reason?: string; [key: string]: unknown };
}
