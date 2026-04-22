import { AwsRum, type AwsRumConfig } from 'aws-rum-web';

interface RumRuntimeConfig {
  appMonitorId: string;
  identityPoolId: string;
  region: string;
}

export function initializeRum(rumConfig?: RumRuntimeConfig) {
  const appMonitorId =
    rumConfig?.appMonitorId || import.meta.env.VITE_RUM_APP_MONITOR_ID;
  const identityPoolId =
    rumConfig?.identityPoolId || import.meta.env.VITE_RUM_IDENTITY_POOL_ID;
  const region = rumConfig?.region || import.meta.env.VITE_RUM_REGION;

  if (!appMonitorId || !identityPoolId || !region) {
    console.log('⏭️ RUM not configured, skipping initialization');
    return;
  }

  try {
    const config: AwsRumConfig = {
      sessionSampleRate: 1,
      identityPoolId,
      endpoint: `https://dataplane.rum.${region}.amazonaws.com`,
      telemetries: [
        'errors',
        'performance',
        'interaction',
        ['http', { addXRayTraceIdHeader: true }],
      ],
      allowCookies: true,
      enableXRay: true,
      pagesToInclude: [/.*/],
    };

    const awsRum = new AwsRum(appMonitorId, '1.0.0', region, config);

    (window as any).awsRum = awsRum;
    awsRum.addSessionAttributes({ userId: 'anonymous' });

    console.log('✅ CloudWatch RUM initialized:', appMonitorId);
  } catch (error) {
    console.error('❌ RUM initialization failed:', error);
  }
}
