import { useRuntimeConfig } from '../../hooks/useRuntimeConfig';
import { useAuth } from 'react-oidc-context';
import { useCallback } from 'react';
import type {
  DDReport,
  HITLFlag,
  Portfolio,
  ProgressEvent,
  Session,
} from './types';

const SAMPLE_PORTFOLIOS: Portfolio[] = [
  {
    portfolio_id: 'pf_amp001',
    name: 'AMP Growth Fund',
    asset_class: 'multi_asset',
    benchmark: 'CPI + 4.5% p.a.',
    aum_aud_m: 2840.0,
  },
  {
    portfolio_id: 'pf_pendal001',
    name: 'Pendal Australian Equities',
    asset_class: 'australian_equities',
    benchmark: 'S&P/ASX 300 Accumulation Index',
    aum_aud_m: 1150.0,
  },
  {
    portfolio_id: 'pf_macq001',
    name: 'Macquarie Income Fund',
    asset_class: 'fixed_income',
    benchmark: 'Bloomberg AusBond Bank Bill Index',
    aum_aud_m: 4200.0,
  },
  {
    portfolio_id: 'pf_aef001',
    name: 'Australian Ethical Balanced',
    asset_class: 'multi_asset',
    benchmark: 'CPI + 3.5% p.a.',
    aum_aud_m: 870.0,
  },
  {
    portfolio_id: 'pf_hyperion001',
    name: 'Hyperion Australian Growth Companies',
    asset_class: 'australian_equities',
    benchmark: 'S&P/ASX All Ordinaries Accumulation Index',
    aum_aud_m: 5100.0,
  },
];

export function useDDApi() {
  const config = useRuntimeConfig();
  const auth = useAuth();
  const baseUrl: string =
    (config as Record<string, unknown> & { apis?: { PortfolioDDApi?: string } })
      .apis?.PortfolioDDApi ?? 'http://localhost:8092';

  const headers = useCallback(
    () => ({
      'Content-Type': 'application/json',
      ...(auth.user?.id_token
        ? { Authorization: `Bearer ${auth.user.id_token}` }
        : {}),
    }),
    [auth.user?.id_token],
  );

  const listPortfolios = useCallback(async (): Promise<Portfolio[]> => {
    try {
      const r = await fetch(`${baseUrl}/dd/portfolios`, { headers: headers() });
      if (!r.ok) return SAMPLE_PORTFOLIOS;
      const d = await r.json();
      return d.portfolios?.length ? d.portfolios : SAMPLE_PORTFOLIOS;
    } catch {
      return SAMPLE_PORTFOLIOS;
    }
  }, [baseUrl, headers]);

  const startReview = useCallback(
    async (portfolioId: string): Promise<Session> => {
      const r = await fetch(`${baseUrl}/dd/sessions`, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({
          portfolio_id: portfolioId,
          initiated_by: auth.user?.profile?.email ?? 'demo',
        }),
      });
      if (!r.ok) throw new Error(await r.text());
      return r.json();
    },
    [baseUrl, headers, auth.user?.profile?.email],
  );

  const getSession = useCallback(
    async (sessionId: string): Promise<Session> => {
      const r = await fetch(`${baseUrl}/dd/sessions/${sessionId}`, {
        headers: headers(),
      });
      if (!r.ok) throw new Error(await r.text());
      return r.json();
    },
    [baseUrl, headers],
  );

  const getReport = useCallback(
    async (sessionId: string): Promise<DDReport> => {
      const r = await fetch(`${baseUrl}/dd/sessions/${sessionId}/report`, {
        headers: headers(),
      });
      if (!r.ok) throw new Error(await r.text());
      return r.json();
    },
    [baseUrl, headers],
  );

  const listFlags = useCallback(
    async (sessionId: string): Promise<HITLFlag[]> => {
      const r = await fetch(`${baseUrl}/dd/sessions/${sessionId}/hitl`, {
        headers: headers(),
      });
      const d = await r.json();
      return d.flags ?? [];
    },
    [baseUrl, headers],
  );

  const resolveFlag = useCallback(
    async (
      sessionId: string,
      flagId: string,
      resolution: string,
      notes: string,
    ): Promise<void> => {
      await fetch(
        `${baseUrl}/dd/sessions/${sessionId}/hitl/${flagId}/resolve`,
        {
          method: 'POST',
          headers: headers(),
          body: JSON.stringify({
            resolution,
            reviewer_notes: notes,
            reviewer: auth.user?.profile?.email ?? '',
          }),
        },
      );
    },
    [baseUrl, headers, auth.user?.profile?.email],
  );

  const getEvents = useCallback(
    async (sessionId: string): Promise<ProgressEvent[]> => {
      try {
        const r = await fetch(`${baseUrl}/dd/sessions/${sessionId}/events`, {
          headers: headers(),
        });
        if (!r.ok) return [];
        const d = await r.json();
        return d.events ?? [];
      } catch {
        return [];
      }
    },
    [baseUrl, headers],
  );

  const listSessions = useCallback(async (): Promise<Session[]> => {
    try {
      const r = await fetch(`${baseUrl}/dd/sessions`, { headers: headers() });
      if (!r.ok) return [];
      const d = await r.json();
      return d.sessions ?? [];
    } catch {
      return [];
    }
  }, [baseUrl, headers]);

  const getReportHtmlUrl = useCallback(
    (sessionId: string): string =>
      `${baseUrl}/dd/sessions/${sessionId}/report/html`,
    [baseUrl],
  );

  const listSourceDocuments = useCallback(
    async (
      portfolioId: string,
    ): Promise<
      { name: string; key: string; type: string; pages?: number }[]
    > => {
      try {
        const r = await fetch(
          `${baseUrl}/dd/portfolios/${portfolioId}/documents`,
          { headers: headers() },
        );
        if (!r.ok) return [];
        const d = await r.json();
        return d.documents ?? [];
      } catch {
        return [];
      }
    },
    [baseUrl, headers],
  );

  const getDocumentUrl = useCallback(
    async (portfolioId: string, docKey: string): Promise<string | null> => {
      try {
        const r = await fetch(
          `${baseUrl}/dd/portfolios/${portfolioId}/documents/url?key=${encodeURIComponent(docKey)}`,
          { headers: headers() },
        );
        if (!r.ok) return null;
        const d = await r.json();
        return d.url ?? null;
      } catch {
        return null;
      }
    },
    [baseUrl, headers],
  );

  return {
    listPortfolios,
    listSessions,
    startReview,
    getSession,
    getReport,
    listFlags,
    resolveFlag,
    getEvents,
    getReportHtmlUrl,
    listSourceDocuments,
    getDocumentUrl,
  };
}
