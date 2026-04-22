import { useQuery } from '@tanstack/react-query';
import { useApi } from './useApi';

export const useClientReport = (clientId: string) => {
  const api = useApi();
  return useQuery(api.clientReport.queryOptions({ clientId }));
};
