import { ReactNode } from 'react';
import { Sidebar } from './Sidebar';
import { UserMenu } from './UserMenu';

export const SearchBox = ({
  value,
  onChange,
  onSearch,
}: {
  value?: string;
  onChange?: (v: string) => void;
  onSearch?: () => void;
}) => (
  <div className="relative">
    <svg
      className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
      />
    </svg>
    <input
      type="text"
      placeholder="Search Anything"
      value={value ?? ''}
      onChange={(e) => onChange?.(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          onSearch?.();
        }
      }}
      className="w-80 pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
    />
  </div>
);

export const PageLayout = ({
  title,
  children,
  headerContent,
}: {
  title: string;
  children: ReactNode;
  headerContent?: ReactNode;
}) => (
  <div className="flex min-h-screen bg-gray-50">
    <Sidebar />
    <div className="flex-1 flex flex-col">
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold text-gray-900">{title}</h1>
          <div className="flex items-center gap-4">
            {headerContent}
            <select className="px-3 py-2 border border-gray-300 rounded-lg bg-white hover:bg-gray-50 transition-colors cursor-pointer text-sm">
              <option value="en">🇺🇸 EN</option>
              <option value="es">🇪🇸 ES</option>
            </select>
            <UserMenu />
          </div>
        </div>
      </div>
      <div className="flex-1 overflow-auto p-6 space-y-4">{children}</div>
    </div>
  </div>
);
