import { useContext } from 'react';
import { ApiContext } from '../components/ApiProvider';
import { ApiOptionsProxy } from '../generated/api/options-proxy.gen';

export const useApi = (): ApiOptionsProxy => {
  const optionsProxy = useContext(ApiContext);

  if (!optionsProxy) {
    throw new Error('useApi must be used within a ApiProvider');
  }

  return optionsProxy;
};
