import React from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider, createRouter } from '@tanstack/react-router';
import { routeTree } from './routeTree.gen';
import './styles.css';
import { initializeRum } from './rum';

const router = createRouter({
  routeTree,
});

// Record page views on navigation
router.subscribe('onLoad', () => {
  const path = router.state.location.pathname;
  console.log('📍 RUM page view:', path);
  (window as any).awsRum?.recordPageView(path);
});

// Register the router instance for type safety
declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}

const root = document.getElementById('root');
if (root) {
  console.log('Root element found, rendering app...');

  // Initialize CloudWatch RUM (from runtime-config.json in prod, env vars in local dev)
  fetch('/runtime-config.json')
    .then((r) => r.json())
    .then((config) => initializeRum(config.rumConfig))
    .catch(() => initializeRum());

  createRoot(root).render(
    <React.StrictMode>
      <RouterProvider router={router} />
    </React.StrictMode>,
  );
} else {
  console.error('Root element not found!');
}
