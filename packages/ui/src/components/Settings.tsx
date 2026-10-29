import { useState } from 'react';
import { useAuth } from 'react-oidc-context';
import { PageLayout } from './PageLayout';

function Toggle({
  enabled,
  onChange,
}: {
  enabled: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      onClick={() => onChange(!enabled)}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
        enabled ? 'bg-blue-600' : 'bg-gray-200'
      }`}
    >
      <span
        className={`inline-block h-4 w-4 rounded-full bg-white transition-transform ${
          enabled ? 'translate-x-6' : 'translate-x-1'
        }`}
      />
    </button>
  );
}

export function SettingsPage() {
  const { user } = useAuth();

  const [emailAlerts, setEmailAlerts] = useState(true);
  const [smsNotifications, setSmsNotifications] = useState(false);
  const [marketAlerts, setMarketAlerts] = useState(true);
  const [complianceReminders, setComplianceReminders] = useState(true);
  const [defaultView, setDefaultView] = useState('mixed');
  const [theme, setTheme] = useState('light');

  const displayName =
    (user?.profile?.given_name as string) ||
    (user?.profile?.['cognito:username'] as string) ||
    'Wealth Advisor';
  const email = (user?.profile?.email as string) || 'advisor@wealthmgmt.demo';
  const initial = displayName.charAt(0).toUpperCase();

  return (
    <PageLayout title="Settings">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* User Profile */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="font-semibold text-gray-800 mb-4">User Profile</h3>
          <div className="flex items-center gap-4 mb-6">
            <div className="w-16 h-16 rounded-full bg-blue-600 flex items-center justify-center text-white text-2xl font-bold">
              {initial}
            </div>
            <div>
              <p className="font-semibold text-lg text-gray-900">
                {displayName}
              </p>
              <p className="text-sm text-gray-500">{email}</p>
            </div>
          </div>
          <div className="space-y-3">
            <div className="flex justify-between items-center py-2 border-b border-gray-50">
              <span className="text-sm text-gray-500">Role</span>
              <span className="text-sm font-medium text-gray-900">
                Senior Wealth Advisor
              </span>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-gray-50">
              <span className="text-sm text-gray-500">Firm</span>
              <span className="text-sm font-medium text-gray-900">
                Meridian Wealth Management
              </span>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-gray-50">
              <span className="text-sm text-gray-500">License</span>
              <span className="text-sm font-medium text-gray-900">
                AFSL #412345
              </span>
            </div>
            <div className="flex justify-between items-center py-2">
              <span className="text-sm text-gray-500">Region</span>
              <span className="text-sm font-medium text-gray-900">
                Sydney, Australia
              </span>
            </div>
          </div>
        </div>

        {/* Notification Preferences */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="font-semibold text-gray-800 mb-4">
            Notification Preferences
          </h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-900">
                  Email Alerts
                </p>
                <p className="text-xs text-gray-500">
                  Receive portfolio alerts via email
                </p>
              </div>
              <Toggle enabled={emailAlerts} onChange={setEmailAlerts} />
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-900">
                  SMS Notifications
                </p>
                <p className="text-xs text-gray-500">
                  Urgent alerts sent via SMS
                </p>
              </div>
              <Toggle
                enabled={smsNotifications}
                onChange={setSmsNotifications}
              />
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-900">
                  Market Alerts
                </p>
                <p className="text-xs text-gray-500">
                  Significant market movements
                </p>
              </div>
              <Toggle enabled={marketAlerts} onChange={setMarketAlerts} />
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-900">
                  Compliance Reminders
                </p>
                <p className="text-xs text-gray-500">
                  Upcoming compliance deadlines
                </p>
              </div>
              <Toggle
                enabled={complianceReminders}
                onChange={setComplianceReminders}
              />
            </div>
          </div>
          <p className="text-xs text-amber-600 mt-4 bg-amber-50 px-3 py-2 rounded">
            Settings are not persisted in demo mode
          </p>
        </div>

        {/* Display Preferences */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="font-semibold text-gray-800 mb-4">
            Display Preferences
          </h3>
          <div className="space-y-4">
            <div>
              <label className="text-sm text-gray-600 block mb-1">
                Dashboard Default View
              </label>
              <select
                value={defaultView}
                onChange={(e) => setDefaultView(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
              >
                <option value="table">Table</option>
                <option value="chart">Chart</option>
                <option value="mixed">Mixed</option>
              </select>
            </div>
            <div>
              <label className="text-sm text-gray-600 block mb-1">Theme</label>
              <select
                value={theme}
                onChange={(e) => setTheme(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
              >
                <option value="light">Light</option>
                <option value="dark">Dark</option>
                <option value="system">System</option>
              </select>
            </div>
          </div>
        </div>

        {/* Platform Info */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="font-semibold text-gray-800 mb-4">Platform Info</h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center py-2 border-b border-gray-50">
              <span className="text-sm text-gray-500">Platform Version</span>
              <span className="text-sm font-mono text-gray-900">1.0.0</span>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-gray-50">
              <span className="text-sm text-gray-500">Region</span>
              <span className="text-sm font-mono text-gray-900">
                ap-southeast-2
              </span>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-gray-50">
              <span className="text-sm text-gray-500">Environment</span>
              <span className="text-sm font-mono text-gray-900">
                Demo (Sandbox)
              </span>
            </div>
            <div className="flex justify-between items-center py-2">
              <span className="text-sm text-gray-500">API Version</span>
              <span className="text-sm font-mono text-gray-900">v1</span>
            </div>
          </div>
        </div>
      </div>
    </PageLayout>
  );
}
