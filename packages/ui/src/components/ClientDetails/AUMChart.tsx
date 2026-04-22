import { memo } from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
} from 'recharts';

interface AUMDataPoint {
  month: string;
  value: number;
}

interface AUMChartProps {
  data: AUMDataPoint[];
  currentAUM: number;
  changePercent: number;
}

export const AUMChart = memo(
  ({ data, currentAUM, changePercent }: AUMChartProps) => {
    const chartData = data.map((d) => ({
      month: new Date(d.month + '-01').toLocaleDateString('en-US', {
        month: 'short',
        year: '2-digit',
      }),
      value: d.value / 1000000,
    }));

    return (
      <div className="bg-white rounded-xl shadow-lg border border-gray-100 hover:shadow-xl transition-shadow p-6">
        <div className="flex items-center justify-between mb-4 pb-3 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-900">
            Assets Under Management
          </h2>
          <span
            className={`text-xs font-medium px-2 py-1 rounded ${changePercent >= 0 ? 'text-green-600 bg-green-50' : 'text-red-600 bg-red-50'}`}
          >
            {changePercent >= 0 ? '+' : ''}
            {changePercent}%
          </span>
        </div>
        <div className="mb-6">
          <div className="text-3xl font-bold text-gray-900 mb-1">
            ${currentAUM.toLocaleString()}
          </div>
          <p className="text-sm text-gray-500">Last 12 months</p>
        </div>
        <div className="h-48">
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={chartData}
                margin={{ top: 10, right: 30, left: -20, bottom: 0 }}
              >
                <defs>
                  <linearGradient
                    id="colorClientAUM"
                    x1="0"
                    y1="0"
                    x2="0"
                    y2="1"
                  >
                    <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis
                  dataKey="month"
                  stroke="#6b7280"
                  style={{ fontSize: '11px' }}
                  interval="preserveStartEnd"
                  angle={-45}
                  textAnchor="end"
                  height={60}
                />
                <YAxis
                  stroke="#6b7280"
                  style={{ fontSize: '13px' }}
                  width={45}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'white',
                    border: '1px solid #e5e7eb',
                    borderRadius: '8px',
                    fontSize: '13px',
                  }}
                  formatter={(value) => [
                    `$${Number(value ?? 0).toFixed(1)}M`,
                    'AUM',
                  ]}
                />
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke="#8b5cf6"
                  strokeWidth={2.5}
                  fillOpacity={1}
                  fill="url(#colorClientAUM)"
                  dot={{ fill: '#8b5cf6', r: 4.5 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-full text-gray-400 text-sm">
              No AUM data available
            </div>
          )}
        </div>
      </div>
    );
  },
);

AUMChart.displayName = 'AUMChart';
