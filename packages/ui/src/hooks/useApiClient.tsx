import { Api } from '../generated/api/client.gen';
import { ApiClientContext } from '../components/ApiProvider';
import { useContext } from 'react';

export const useApiClient = (): Api => {
  const client = useContext(ApiClientContext);

  if (!client) {
    throw new Error('useApiClient must be used within a ApiProvider');
  }

  return client;
};
