import { useNavigate } from '@tanstack/react-router';
import { useEffect, useRef, useState } from 'react';

interface GraphNode {
  id: string;
  label: string;
  type: string;
  properties?: Record<string, any>;
}

interface ClientGraphViewProps {
  clients: any[];
}

export function ClientGraphView({ clients }: ClientGraphViewProps) {
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<any>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [isReady, setIsReady] = useState(false);

  // Load vis-network script once on mount
  useEffect(() => {
    if ((window as any).vis) {
      setIsReady(true);
      return;
    }

    const script = document.createElement('script');
    script.src =
      'https://unpkg.com/vis-network/standalone/umd/vis-network.min.js';
    script.async = true;
    script.onload = () => {
      setIsReady(true);
    };
    script.onerror = () => {
      console.error('Failed to load vis-network library');
    };
    document.body.appendChild(script);

    return () => {
      if (networkRef.current) {
        networkRef.current.destroy();
        networkRef.current = null;
      }
    };
  }, []);

  // Initialize graph when ready and clients are available
  useEffect(() => {
    if (
      !isReady ||
      !containerRef.current ||
      clients.length === 0 ||
      networkRef.current
    ) {
      return;
    }

    // Destroy existing network if any
    if (networkRef.current) {
      try {
        networkRef.current.destroy();
      } catch (e) {
        console.warn('Error destroying network:', e);
      }
      networkRef.current = null;
    }

    initGraph();

    return () => {
      if (networkRef.current) {
        try {
          networkRef.current.destroy();
        } catch (e) {
          console.warn('Error destroying network on cleanup:', e);
        }
        networkRef.current = null;
      }
    };
  }, [isReady, clients]);

  const initGraph = () => {
    if (!containerRef.current || !(window as any).vis) {
      console.error('Container or vis not available');
      return;
    }

    const vis = (window as any).vis;

    try {
      // Deduplicate clients by client_id (keep first occurrence)
      const uniqueClients = Array.from(
        new Map(clients.map((c) => [c.client_id, c])).values(),
      );

      // Create nodes from clients
      const nodesArray = uniqueClients.map((client) => {
        const value = client.net_worth || client.aum || 1000000;
        const nodeSize = Math.max(30, Math.min(60, value / 100000));
        return {
          id: client.client_id,
          label: client.customer_name || 'Unknown',
          title: `${client.customer_name}\nSegment: ${client.segment || 'N/A'}\nNet Worth: $${(value || 0).toLocaleString()}`,
          color: {
            background: getSegmentColor(client.segment),
            border: '#3b82f6',
            highlight: {
              background: '#3b82f6',
              border: '#1e40af',
            },
          },
          font: { color: '#fff', size: 14 },
          shape: 'dot',
          size: nodeSize,
        };
      });

      // Create edges (connections between clients)
      // Connect clients in the same segment (sample to avoid too many edges)
      const edgesArray: any[] = [];

      uniqueClients.forEach((client, i) => {
        uniqueClients.slice(i + 1).forEach((otherClient) => {
          // Connect if same segment (30% probability to avoid clutter)
          if (
            client.segment &&
            client.segment === otherClient.segment &&
            Math.random() < 0.3
          ) {
            edgesArray.push({
              from: client.client_id,
              to: otherClient.client_id,
              color: { color: '#cbd5e1' },
              width: 1,
            });
          }
        });
      });

      // Create DataSets
      let nodesDataSet, edgesDataSet;
      try {
        nodesDataSet = new vis.DataSet(nodesArray);
        edgesDataSet = new vis.DataSet(edgesArray);
      } catch (error) {
        console.error('Error creating DataSets:', error);
        return;
      }

      const data = {
        nodes: nodesDataSet,
        edges: edgesDataSet,
      };

      const options = {
        nodes: {
          font: {
            size: 14,
            color: '#fff',
          },
        },
        edges: {
          color: { color: '#64748b', highlight: '#3b82f6' },
          width: 3,
          smooth: {
            type: 'continuous',
          },
          chosen: {
            edge: true,
          },
        },
        physics: {
          enabled: true,
          stabilization: {
            iterations: 100,
          },
          barnesHut: {
            gravitationalConstant: -2000,
            springConstant: 0.001,
            springLength: 200,
          },
        },
        interaction: {
          hover: true,
          tooltipDelay: 100,
        },
      };

      const network = new vis.Network(containerRef.current, data, options);
      networkRef.current = network;

      // Handle node clicks
      network.on('click', (params: any) => {
        if (params.nodes.length > 0) {
          const clientId = params.nodes[0];
          const client = clients.find((c) => c.client_id === clientId);
          if (client) {
            // Navigate to client details
            navigate({ to: '/clients/$clientId', params: { clientId } });
          }
        }
      });

      // Handle node selection for detail panel
      network.on('selectNode', (params: any) => {
        if (params.nodes.length > 0) {
          const clientId = params.nodes[0];
          const client = clients.find((c) => c.client_id === clientId);
          if (client) {
            setSelectedNode({
              id: client.client_id,
              label: client.customer_name,
              type: 'Client',
              properties: {
                segment: client.segment,
                net_worth: client.net_worth,
                risk_tolerance: client.risk_tolerance,
                ytd_performance: client.ytd_perf,
                interaction_sentiment: client.interaction_sentiment,
              },
            });
          }
        }
      });

      network.on('deselectNode', () => {
        setSelectedNode(null);
      });
    } catch (error) {
      console.error('Error initializing graph:', error);
    }
  };

  const getSegmentColor = (segment: string | undefined) => {
    const colors: Record<string, string> = {
      HNW: '#10b981',
      'High Net Worth': '#10b981',
      UHNW: '#8b5cf6',
      'Ultra High Net Worth': '#8b5cf6',
      'Mass Affluent': '#3b82f6',
      'Emerging Affluent': '#f59e0b',
    };
    return colors[segment || ''] || '#6b7280';
  };

  return (
    <div className="flex h-full w-full">
      <div className="flex-1 relative bg-gray-50 h-full">
        <div ref={containerRef} className="w-full h-full" />

        {/* Legend */}
        <div className="absolute top-4 left-4 bg-white rounded-lg shadow-lg p-4 max-w-xs">
          <h3 className="font-semibold text-sm mb-3">Client Segments</h3>
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-[#8b5cf6]"></div>
              <span className="text-sm">Ultra High Net Worth</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-[#10b981]"></div>
              <span className="text-sm">High Net Worth</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-[#3b82f6]"></div>
              <span className="text-sm">Mass Affluent</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-[#f59e0b]"></div>
              <span className="text-sm">Emerging Affluent</span>
            </div>
          </div>
          <p className="text-xs text-gray-500 mt-3">
            Node size represents AUM. Click any node to view details.
          </p>
        </div>
      </div>

      {/* Detail Panel */}
      {selectedNode && (
        <div className="w-80 bg-white border-l border-gray-200 p-6 overflow-y-auto">
          <div className="flex justify-between items-start mb-4">
            <div>
              <span className="inline-block px-3 py-1 bg-blue-100 text-blue-800 text-xs font-semibold rounded-full mb-2">
                {selectedNode.type}
              </span>
              <h3 className="text-lg font-semibold">{selectedNode.label}</h3>
            </div>
            <button
              onClick={() => setSelectedNode(null)}
              className="text-gray-400 hover:text-gray-600"
            >
              ✕
            </button>
          </div>

          <div className="space-y-4">
            {selectedNode.properties &&
              Object.entries(selectedNode.properties).map(([key, value]) => (
                <div key={key}>
                  <div className="text-xs text-gray-500 uppercase mb-1">
                    {key.replace(/_/g, ' ')}
                  </div>
                  <div className="text-sm font-medium">
                    {key === 'net_worth' && typeof value === 'number'
                      ? `$${value.toLocaleString()}`
                      : String(value || 'N/A')}
                  </div>
                </div>
              ))}
          </div>

          <button
            onClick={() =>
              navigate({
                to: '/clients/$clientId',
                params: { clientId: selectedNode.id },
              })
            }
            className="w-full mt-6 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            View Full Details
          </button>
        </div>
      )}
    </div>
  );
}
