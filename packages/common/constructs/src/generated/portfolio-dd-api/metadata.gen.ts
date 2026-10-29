/**
 * Operation details for PortfolioDDApi
 */
export const OPERATION_DETAILS = {
  listPortfolios: {
    path: '/dd/portfolios',
    method: 'GET',
  },
  startReview: {
    path: '/dd/sessions',
    method: 'POST',
  },
  getSession: {
    path: '/dd/sessions/{sessionId}',
    method: 'GET',
  },
  getEvents: {
    path: '/dd/sessions/{sessionId}/events',
    method: 'GET',
  },
  getReport: {
    path: '/dd/sessions/{sessionId}/report',
    method: 'GET',
  },
  listHitlFlags: {
    path: '/dd/sessions/{sessionId}/hitl',
    method: 'GET',
  },
  resolveHitlFlag: {
    path: '/dd/sessions/{sessionId}/hitl/{flagId}/resolve',
    method: 'POST',
  },
} as const;

/**
 * Type for all operation names as a string union
 */
export type Operations = keyof typeof OPERATION_DETAILS;
