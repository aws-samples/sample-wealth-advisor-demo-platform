/**
 * Operation details for Api
 */
export const OPERATION_DETAILS = {
  aumTrends: {
    path: '/aum-trends',
    method: 'GET',
  },
  clientAssetAllocation: {
    path: '/clients/{client_id}/asset-allocation',
    method: 'GET',
  },
  clientAum: {
    path: '/clients/{client_id}/aum',
    method: 'GET',
  },
  clientDetails: {
    path: '/clients/{client_id}',
    method: 'GET',
  },
  clientHoldings: {
    path: '/clients/{client_id}/holdings',
    method: 'GET',
  },
  clientReport: {
    path: '/clients/{client_id}/report',
    method: 'GET',
  },
  clientSearch: {
    path: '/clients/search',
    method: 'POST',
  },
  clientSegments: {
    path: '/client-segments',
    method: 'GET',
  },
  clientThemes: {
    path: '/clients/{client_id}/themes',
    method: 'GET',
  },
  clientTransactions: {
    path: '/clients/{client_id}/transactions',
    method: 'GET',
  },
  clients: {
    path: '/clients',
    method: 'GET',
  },
  dashboardSummary: {
    path: '/dashboard-summary',
    method: 'GET',
  },
  echo: {
    path: '/echo',
    method: 'GET',
  },
  generateReport: {
    path: '/clients/{client_id}/report/generate',
    method: 'POST',
  },
  marketThemes: {
    path: '/market-themes',
    method: 'GET',
  },
  marketThemesRefresh: {
    path: '/market-themes/refresh',
    method: 'POST',
  },
  portfolioSummary: {
    path: '/portfolio-summary',
    method: 'GET',
  },
  reportsSummary: {
    path: '/reports/summary',
    method: 'GET',
  },
  themeArticles: {
    path: '/market-themes/{theme_id}/articles',
    method: 'GET',
  },
  topClients: {
    path: '/top-clients',
    method: 'GET',
  },
} as const;

/**
 * Type for all operation names as a string union
 */
export type Operations = keyof typeof OPERATION_DETAILS;
