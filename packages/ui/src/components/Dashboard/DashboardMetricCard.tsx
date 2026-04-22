import { memo } from 'react';

interface DashboardMetricCardProps {
  title: string;
  value: string;
  change: string;
  icon: string;
}

export const DashboardMetricCard = memo(
  ({ title, value, change, icon }: DashboardMetricCardProps) => (
    <div className="bg-white rounded-lg shadow p-6 hover:shadow-lg transition-shadow">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-gray-600">{title}</h3>
        <svg
          className="w-8 h-8 text-blue-600"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d={icon}
          />
        </svg>
      </div>
      <div className="text-3xl font-bold text-gray-900 mb-2">{value}</div>
      <p className="text-sm text-gray-500">{change}</p>
    </div>
  ),
);

DashboardMetricCard.displayName = 'DashboardMetricCard';
