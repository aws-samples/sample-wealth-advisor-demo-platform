import { useContext } from 'react';
import {
  RuntimeConfigContext,
  IRuntimeConfig,
} from '../components/RuntimeConfig';

export interface TypedRuntimeConfig extends IRuntimeConfig {
  apis: {
    Api: string;
    IntelligenceApi: string;
    GraphSearchApi: string;
  };
  apiUrl: string;
  intelligenceApiUrl: string;
  graphSearchApiUrl: string;
  graphSearchAgentArn: string;
  routingAgentArn: string;
  voiceGatewayArn: string;
}

export const useRuntimeConfig = (): TypedRuntimeConfig => {
  const runtimeConfig = useContext(RuntimeConfigContext);

  if (!runtimeConfig) {
    throw new Error(
      'useRuntimeConfig must be used within a RuntimeConfigProvider',
    );
  }

  return {
    ...runtimeConfig,
    apiUrl: runtimeConfig.apis?.Api || '',
    intelligenceApiUrl: runtimeConfig.apis?.IntelligenceApi || '',
    graphSearchApiUrl: runtimeConfig.apis?.GraphSearchApi || '',
    graphSearchAgentArn: runtimeConfig.graphSearchAgentArn || '',
    routingAgentArn: runtimeConfig.routingAgentArn || '',
    voiceGatewayArn: runtimeConfig.voiceGatewayArn || '',
  };
};
