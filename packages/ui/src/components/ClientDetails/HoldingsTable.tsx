import { memo, useCallback } from 'react';

interface Holding {
  ticker: string;
  companyName: string;
  shares: number;
  currentPrice: number;
  currentValue: number;
  unrealizedGainLoss: number;
}

interface HoldingsTableProps {
  holdings: Holding[];
  hasMore: boolean;
  offset: number;
  onLoadMore: (newOffset: number) => void;
}

export const HoldingsTable = memo(
  ({ holdings, hasMore, offset, onLoadMore }: HoldingsTableProps) => {
    const handlePrevious = useCallback(() => {
      onLoadMore(Math.max(0, offset - 20));
    }, [offset, onLoadMore]);

    const handleNext = useCallback(() => {
      onLoadMore(offset + 20);
    }, [offset, onLoadMore]);

    return (
      <div className="bg-white rounded-lg shadow mb-6 mt-6">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">
            Portfolio Holdings
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-4 text-left text-xs font-bold text-gray-700 uppercase">
                  Symbol
                </th>
                <th className="px-6 py-4 text-left text-xs font-bold text-gray-700 uppercase">
                  Company
                </th>
                <th className="px-6 py-4 text-right text-xs font-bold text-gray-700 uppercase">
                  Shares
                </th>
                <th className="px-6 py-4 text-right text-xs font-bold text-gray-700 uppercase">
                  Price
                </th>
                <th className="px-6 py-4 text-right text-xs font-bold text-gray-700 uppercase">
                  Value
                </th>
                <th className="px-6 py-4 text-right text-xs font-bold text-gray-700 uppercase">
                  Change
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {holdings.length > 0 ? (
                holdings.map((holding, index) => (
                  <tr key={index} className="hover:bg-gray-50">
                    <td className="px-6 py-4 font-bold text-gray-900">
                      {holding.ticker}
                    </td>
                    <td className="px-6 py-4 text-gray-700">
                      {holding.companyName}
                    </td>
                    <td className="px-6 py-4 text-right font-medium text-gray-900">
                      {(holding.shares ?? 0).toFixed(3)}
                    </td>
                    <td className="px-6 py-4 text-right font-medium text-gray-900">
                      ${(holding.currentPrice ?? 0).toFixed(2)}
                    </td>
                    <td className="px-6 py-4 text-right font-bold text-gray-900">
                      $
                      {(holding.currentValue ?? 0).toLocaleString('en-US', {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}
                    </td>
                    <td
                      className={`px-6 py-4 text-right font-bold ${(holding.unrealizedGainLoss ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}
                    >
                      {(holding.unrealizedGainLoss ?? 0) >= 0 ? '+' : ''}$
                      {Math.abs(holding.unrealizedGainLoss ?? 0).toLocaleString(
                        'en-US',
                        { minimumFractionDigits: 2, maximumFractionDigits: 2 },
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td
                    colSpan={6}
                    className="px-6 py-8 text-center text-gray-500"
                  >
                    No holdings found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {hasMore && (
          <div className="px-6 pb-4 flex items-center justify-center gap-2">
            {offset > 0 && (
              <button
                onClick={handlePrevious}
                className="px-3 py-1 text-sm text-blue-600 hover:bg-blue-50 rounded"
              >
                ← Previous
              </button>
            )}
            <span className="text-sm text-gray-600">
              Page {Math.floor(offset / 10) + 1}
            </span>
            <button
              onClick={handleNext}
              className="px-3 py-1 text-sm text-blue-600 hover:bg-blue-50 rounded"
            >
              Next →
            </button>
          </div>
        )}
      </div>
    );
  },
);

HoldingsTable.displayName = 'HoldingsTable';
