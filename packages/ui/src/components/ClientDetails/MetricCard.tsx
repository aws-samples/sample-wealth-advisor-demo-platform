import { memo } from 'react';

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: React.ReactNode;
  onClick?: () => void;
}

export const MetricCard = memo(
  ({ title, value, subtitle, icon, onClick }: MetricCardProps) => (
    <div className="bg-white rounded-lg shadow p-4 flex flex-col items-center justify-center text-center">
      {icon}
      <p className="text-xs text-gray-500 mb-1">{title}</p>
      <p className="text-xl font-bold text-blue-600">{value}</p>
      {subtitle && (
        <p className="text-[10px] text-gray-400 mt-0.5">{subtitle}</p>
      )}
      {onClick && (
        <button
          onClick={onClick}
          className="text-xs text-blue-600 hover:text-blue-700 mt-1"
        >
          View Details
        </button>
      )}
    </div>
  ),
);

MetricCard.displayName = 'MetricCard';
