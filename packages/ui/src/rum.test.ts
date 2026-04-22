import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockAddSessionAttributes = vi.fn();
const mockRecordPageView = vi.fn();
const mockAwsRum = vi.fn().mockImplementation(function () {
  (this as any).addSessionAttributes = mockAddSessionAttributes;
  (this as any).recordPageView = mockRecordPageView;
});

vi.mock('aws-rum-web', () => ({
  AwsRum: mockAwsRum,
}));

describe('RUM Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
    delete (window as any).awsRum;
    vi.stubEnv('VITE_RUM_APP_MONITOR_ID', 'test-app-id');
    vi.stubEnv('VITE_RUM_IDENTITY_POOL_ID', 'us-west-2:test-pool');
    vi.stubEnv('VITE_RUM_REGION', 'us-west-2');
  });

  it('initializes AwsRum with correct config', async () => {
    const { initializeRum } = await import('./rum');
    initializeRum();

    expect(mockAwsRum).toHaveBeenCalledWith(
      'test-app-id',
      '1.0.0',
      'us-west-2',
      expect.objectContaining({
        sessionSampleRate: 1,
        identityPoolId: 'us-west-2:test-pool',
        endpoint: 'https://dataplane.rum.us-west-2.amazonaws.com',
        enableXRay: true,
        allowCookies: true,
      }),
    );
    const config = mockAwsRum.mock.calls[0][3];
    expect(config.pagesToInclude).toHaveLength(1);
    expect(config.pagesToInclude[0]).toBeInstanceOf(RegExp);
  });

  it('enables X-Ray trace headers on HTTP telemetry', async () => {
    const { initializeRum } = await import('./rum');
    initializeRum();

    const config = mockAwsRum.mock.calls[0][3];
    expect(config.telemetries).toContainEqual([
      'http',
      { addXRayTraceIdHeader: true },
    ]);
  });

  it('includes interaction telemetry', async () => {
    const { initializeRum } = await import('./rum');
    initializeRum();

    const config = mockAwsRum.mock.calls[0][3];
    expect(config.telemetries).toContain('interaction');
  });

  it('exposes awsRum on window', async () => {
    const { initializeRum } = await import('./rum');
    initializeRum();

    expect((window as any).awsRum).toBeDefined();
  });

  it('sets anonymous userId session attribute', async () => {
    const { initializeRum } = await import('./rum');
    initializeRum();

    expect(mockAddSessionAttributes).toHaveBeenCalledWith({
      userId: 'anonymous',
    });
  });

  it('handles initialization errors gracefully', async () => {
    mockAwsRum.mockImplementation(() => {
      throw new Error('init failed');
    });
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {
      // noop
    });

    const { initializeRum } = await import('./rum');
    initializeRum();

    expect(consoleSpy).toHaveBeenCalledWith(
      '❌ RUM initialization failed:',
      expect.any(Error),
    );
    expect((window as any).awsRum).toBeUndefined();
    consoleSpy.mockRestore();
    mockAwsRum.mockImplementation(function () {
      (this as any).addSessionAttributes = mockAddSessionAttributes;
      (this as any).recordPageView = mockRecordPageView;
    });
  });
});
