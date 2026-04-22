import { memo } from 'react';

interface Alert {
  id: string;
  type: 'compliance' | 'market' | 'scheduled';
  title: string;
  message: string;
  severity: 'high' | 'medium' | 'low';
}

const severityColors = {
  high: 'bg-red-50 border-red-500',
  medium: 'bg-amber-50 border-amber-500',
  low: 'bg-blue-50 border-blue-500',
};

const severityDotColors = {
  high: 'bg-red-500',
  medium: 'bg-amber-500',
  low: 'bg-blue-500',
};

export const AlertsPanel = memo(({ alerts }: { alerts: Alert[] }) => (
  <div className="bg-white rounded-xl shadow-lg border border-gray-100 hover:shadow-xl transition-shadow p-6 h-full">
    <h2 className="text-lg font-bold text-gray-900 mb-6 pb-4 border-b-2 border-blue-500">
      Alerts & Events
    </h2>
    <div className="space-y-3">
      {alerts.map((alert) => (
        <div
          key={alert.id}
          className={`${severityColors[alert.severity]} border-l-4 p-3 rounded-r`}
        >
          <div className="flex items-start gap-3">
            <div
              className={`flex-shrink-0 w-2 h-2 rounded-full ${severityDotColors[alert.severity]} mt-1.5`}
            />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-gray-900 mb-1">
                {alert.title}
              </p>
              <p className="text-xs text-gray-600">{alert.message}</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  </div>
));

AlertsPanel.displayName = 'AlertsPanel';
