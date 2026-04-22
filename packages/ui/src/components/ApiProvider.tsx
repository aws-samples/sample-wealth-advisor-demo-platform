import {
  createContext,
  FC,
  PropsWithChildren,
  useMemo,
  useCallback,
} from 'react';
import { Api } from '../generated/api/client.gen';
import { ApiOptionsProxy } from '../generated/api/options-proxy.gen';
import { useRuntimeConfig } from '../hooks/useRuntimeConfig';
import { useAuth } from 'react-oidc-context';

export const ApiContext = createContext<ApiOptionsProxy | undefined>(undefined);

export const ApiClientContext = createContext<Api | undefined>(undefined);

const useCreateApiClient = (): Api => {
  const runtimeConfig = useRuntimeConfig();
  const apiUrl = runtimeConfig.apis.Api;
  const auth = useAuth();
  const user = auth?.user;

  const cognitoClient = useCallback<typeof fetch>(
    (url, init) => {
      const headers = { Authorization: `Bearer ${user?.id_token}` };
      const existingHeaders = init?.headers;

      return fetch(url, {
        ...init,
        headers: !existingHeaders
          ? headers
          : existingHeaders instanceof Headers
            ? (() => {
                const h = new Headers(existingHeaders);
                Object.entries(headers).forEach(([k, v]) => h.append(k, v));
                return h;
              })()
            : Array.isArray(existingHeaders)
              ? [...existingHeaders, ...Object.entries(headers)]
              : { ...existingHeaders, ...headers },
      });
    },
    [user?.id_token],
  );

  return useMemo(
    () =>
      new Api({
        url: apiUrl,
        fetch: cognitoClient,
      }),
    [apiUrl, cognitoClient],
  );
};

export const ApiProvider: FC<PropsWithChildren> = ({ children }) => {
  const client = useCreateApiClient();
  const optionsProxy = useMemo(() => new ApiOptionsProxy({ client }), [client]);

  return (
    <ApiClientContext.Provider value={client}>
      <ApiContext.Provider value={optionsProxy}>{children}</ApiContext.Provider>
    </ApiClientContext.Provider>
  );
};

export default ApiProvider;
