import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Input } from ':wealth-management-portal/common-shadcn/components/ui/input';
import { Button } from ':wealth-management-portal/common-shadcn/components/ui/button';
import { SelectionTooltip } from './SelectionTooltip';
import { GraphResultsTable } from './GraphResultsTable';
import type { GraphConfig } from './types';
import type { EnrichedSearchResponse } from './types';
import type { GraphStatus } from '../../hooks/useGraphSearch';

interface Props {
  config: GraphConfig;
  filters: Record<string, boolean>;
  status: GraphStatus;
  searching: boolean;
  searchStatus: string;
  searchResults: EnrichedSearchResponse | null;
  streamingReasoning: string;
  onToggleFilter: (type: string) => void;
  onSearch: (query: string) => void;
  onFocusNode: (nodeId: string) => void;
  onLoadData: () => void;
  onRefresh: () => void;
  onCollapse: () => void;
}

export function GraphSearchSidebar({
  config,
  filters,
  status,
  searching,
  searchStatus,
  searchResults,
  streamingReasoning,
  onToggleFilter,
  onSearch,
  onFocusNode,
  onLoadData,
  onRefresh,
  onCollapse,
}: Props) {
  const [query, setQuery] = useState('');
  const [filtersOpen, setFiltersOpen] = useState(true);
  const [neptuneOpen, setNeptuneOpen] = useState(false);

  const handleSearch = () => {
    if (query.trim()) onSearch(query);
  };

  return (
    <aside className="h-full bg-white border-r border-slate-200 flex flex-col overflow-y-auto">
      {/* Header */}
      <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
        <div>
          <h1 className="text-base font-semibold text-slate-800 tracking-tight">
            Knowledge Graph
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Financial Advisor Network
          </p>
        </div>
        <button
          onClick={onCollapse}
          className="w-7 h-7 flex items-center justify-center rounded-md hover:bg-slate-100 text-slate-400 transition-colors"
          title="Collapse sidebar"
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          >
            <path d="M12 2v12M9 5l-3 3 3 3" />
          </svg>
        </button>
      </div>

      {/* AI Search */}
      <div className="px-5 py-4 border-b border-slate-100">
        <div className="relative">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="Ask about your network…"
            className="pr-10 bg-slate-50 border-slate-200 focus:bg-white text-sm"
          />
          <button
            onClick={handleSearch}
            disabled={searching || !query.trim()}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-blue-500 disabled:opacity-30 transition-colors"
            title="Search"
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            >
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.3-4.3" />
            </svg>
          </button>
        </div>

        <Button
          className="w-full mt-2 text-xs h-8"
          onClick={handleSearch}
          disabled={searching || !query.trim()}
        >
          {searching ? 'Searching…' : 'Search with AI'}
        </Button>

        {/* Live search status */}
        {searching && searchStatus && (
          <div className="flex items-center gap-2 mt-3 py-1">
            <div className="w-3.5 h-3.5 border-2 border-slate-200 border-t-blue-500 rounded-full animate-spin flex-shrink-0" />
            <span className="text-xs text-slate-500">{searchStatus}</span>
          </div>
        )}

        {/* Streaming reasoning tokens */}
        {searching && streamingReasoning && (
          <div
            className="mt-2 p-3 bg-slate-50 rounded-lg text-xs text-slate-600 leading-relaxed
            [&_h1]:text-sm [&_h1]:font-semibold [&_h1]:text-slate-800 [&_h1]:mt-2 [&_h1]:mb-1
            [&_h2]:text-sm [&_h2]:font-semibold [&_h2]:text-slate-800 [&_h2]:mt-2 [&_h2]:mb-1
            [&_h3]:text-xs [&_h3]:font-semibold [&_h3]:text-slate-700 [&_h3]:mt-2 [&_h3]:mb-1
            [&_strong]:text-slate-700 [&_strong]:font-semibold
            [&_ul]:ml-3 [&_ul]:list-disc [&_ol]:ml-3 [&_ol]:list-decimal
            [&_li]:mt-0.5 [&_p]:mt-1"
          >
            <ReactMarkdown>{streamingReasoning}</ReactMarkdown>
          </div>
        )}

        {/* Search results */}
        {!searching && searchResults && (
          <div className="mt-3">
            {searchResults.matching_ids?.length ? (
              <>
                <p className="text-xs text-emerald-600 font-medium">
                  Found {searchResults.matching_ids.length} result(s)
                </p>
                {(searchResults.reasoning || searchResults.explanation) && (
                  <div
                    className="insight-box mt-2 p-3 bg-slate-50 rounded-lg text-xs text-slate-600 leading-relaxed
                    [&_h1]:text-sm [&_h1]:font-semibold [&_h1]:text-slate-800 [&_h1]:mt-2 [&_h1]:mb-1
                    [&_h2]:text-sm [&_h2]:font-semibold [&_h2]:text-slate-800 [&_h2]:mt-2 [&_h2]:mb-1
                    [&_h3]:text-xs [&_h3]:font-semibold [&_h3]:text-slate-700 [&_h3]:mt-2 [&_h3]:mb-1
                    [&_strong]:text-slate-700 [&_strong]:font-semibold
                    [&_ul]:ml-3 [&_ul]:list-disc [&_ol]:ml-3 [&_ol]:list-decimal
                    [&_li]:mt-0.5 [&_p]:mt-1"
                  >
                    <ReactMarkdown>
                      {searchResults.reasoning ||
                        searchResults.explanation ||
                        ''}
                    </ReactMarkdown>
                  </div>
                )}
              </>
            ) : (
              <p className="text-xs text-amber-500">
                {searchResults.explanation ||
                  'No results found. Try a different query.'}
              </p>
            )}

            {searchResults.enriched_nodes?.length ? (
              <div className="mt-2">
                <GraphResultsTable
                  config={config}
                  data={searchResults}
                  searching={false}
                  onFocusNode={onFocusNode}
                />
              </div>
            ) : null}
          </div>
        )}

        {/* Example queries */}
        {config.examples.length > 0 && (
          <div className="mt-3">
            <span className="text-xs font-medium text-slate-500">Try</span>
            <ul className="mt-1.5 list-none space-y-1.5">
              {config.examples.map((ex: string) => {
                const colonIdx = ex.indexOf(':');
                const category =
                  colonIdx > 0 ? ex.slice(0, colonIdx).trim() : '';
                const queryText =
                  colonIdx > 0 ? ex.slice(colonIdx + 1).trim() : ex;
                return (
                  <li key={ex}>
                    {category && (
                      <span className="block text-[0.65rem] text-slate-400 uppercase tracking-wide">
                        {category}
                      </span>
                    )}
                    <span
                      className="text-xs text-blue-500 cursor-pointer hover:underline leading-snug"
                      onClick={() => setQuery(queryText)}
                    >
                      {queryText}
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </div>

      {/* Filter by Type — collapsible */}
      <div className="border-b border-slate-100">
        <button
          onClick={() => setFiltersOpen(!filtersOpen)}
          className="w-full px-5 py-3 flex items-center justify-between text-xs font-semibold text-slate-400 uppercase tracking-wider hover:bg-slate-50 transition-colors"
        >
          Entity Types
          <svg
            width="12"
            height="12"
            viewBox="0 0 12 12"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            className={`transition-transform ${filtersOpen ? 'rotate-180' : ''}`}
          >
            <path d="M3 4.5l3 3 3-3" />
          </svg>
        </button>
        {filtersOpen && (
          <div className="px-5 pb-3 space-y-0.5">
            {Object.entries(config.colors).map(([type, color]) => (
              <label
                key={type}
                className="flex items-center py-1.5 px-2 rounded-md hover:bg-slate-50 cursor-pointer transition-colors"
              >
                <span
                  className="w-2.5 h-2.5 rounded-full mr-2.5 flex-shrink-0"
                  style={{ backgroundColor: color as string }}
                />
                <span className="text-sm text-slate-600 flex-1">
                  {type.replace(/([a-z])([A-Z])/g, '$1 $2')}
                </span>
                <input
                  type="checkbox"
                  checked={filters[type] ?? true}
                  onChange={() => onToggleFilter(type)}
                  className="accent-blue-500"
                />
              </label>
            ))}
          </div>
        )}
      </div>

      {/* Neptune Analytics — collapsible */}
      <div className="border-b border-slate-100">
        <button
          onClick={() => setNeptuneOpen(!neptuneOpen)}
          className="w-full px-5 py-3 flex items-center justify-between text-xs font-semibold text-slate-400 uppercase tracking-wider hover:bg-slate-50 transition-colors"
        >
          Data Source
          <svg
            width="12"
            height="12"
            viewBox="0 0 12 12"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            className={`transition-transform ${neptuneOpen ? 'rotate-180' : ''}`}
          >
            <path d="M3 4.5l3 3 3-3" />
          </svg>
        </button>
        {neptuneOpen && (
          <div className="px-5 pb-3 space-y-2">
            <Button
              variant="outline"
              className="w-full text-xs h-8"
              onClick={onLoadData}
            >
              Load Data
            </Button>
            <Button
              variant="outline"
              className="w-full text-xs h-8"
              onClick={onRefresh}
            >
              Refresh
            </Button>
            {status.message && (
              <p
                className={`text-xs ${
                  status.type === 'ok'
                    ? 'text-emerald-600'
                    : status.type === 'warn'
                      ? 'text-amber-500'
                      : status.type === 'err'
                        ? 'text-red-500'
                        : 'text-slate-400'
                }`}
              >
                {status.message}
              </p>
            )}
          </div>
        )}
      </div>

      <SelectionTooltip
        containerSelector=".insight-box"
        onSearch={(q) => {
          setQuery(q);
          onSearch(q);
        }}
      />
    </aside>
  );
}
