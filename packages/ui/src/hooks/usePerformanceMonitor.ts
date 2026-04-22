import { useEffect } from 'react';

export const usePerformanceMonitor = (componentName: string): void => {
  useEffect(() => {
    if (process.env.NODE_ENV !== 'development') {
      return undefined;
    }

    const startTime = performance.now();

    return () => {
      const endTime = performance.now();
      const renderTime = endTime - startTime;

      if (renderTime > 16) {
        // More than one frame (60fps)
        console.warn(
          `[Performance] ${componentName} took ${renderTime.toFixed(2)}ms to render`,
        );
      }
    };
  }, [componentName]);
};

export const measureAsync = async <T>(
  name: string,
  fn: () => Promise<T>,
): Promise<T> => {
  const start = performance.now();
  try {
    return await fn();
  } finally {
    const duration = performance.now() - start;
    if (process.env.NODE_ENV === 'development') {
      console.log(`[Performance] ${name} took ${duration.toFixed(2)}ms`);
    }
  }
};
