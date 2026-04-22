import { useEffect, useRef, useState } from 'react';
import { useAuth } from 'react-oidc-context';
import * as React from 'react';
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from ':wealth-management-portal/common-shadcn/components/ui/sidebar';
import { Separator } from ':wealth-management-portal/common-shadcn/components/ui/separator';
import Config from '../../config';

import { Link, useLocation, useMatchRoute } from '@tanstack/react-router';
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from ':wealth-management-portal/common-shadcn/components/ui/breadcrumb';
import { AppSidebar } from '../app-sidebar';
import { ImprovedChatWidget } from '../ImprovedChatWidget';

const getBreadcrumbs = (
  matchRoute: ReturnType<typeof useMatchRoute>,
  pathName: string,
  search: string,
  defaultBreadcrumb: string,
  availableRoutes?: string[],
) => {
  const segments = [
    defaultBreadcrumb,
    ...pathName.split('/').filter((segment) => segment !== ''),
  ];

  return segments.map((segment, i) => {
    const href =
      i === 0
        ? '/'
        : `/${segments
            .slice(1, i + 1)
            .join('/')
            .replace('//', '/')}`;

    const matched =
      !availableRoutes || availableRoutes.find((r) => matchRoute({ to: href }));

    return {
      href: matched ? `${href}${search}` : '#',
      text: segment,
    };
  });
};

const AppLayout = ({ children }: { children: React.ReactNode }) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as any)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);
  const { user, removeUser, signoutRedirect, clearStaleState } = useAuth();
  const [activeBreadcrumbs, setActiveBreadcrumbs] = React.useState<
    {
      href: string;
      text: string;
    }[]
  >([{ text: '/', href: '/' }]);
  const matchRoute = useMatchRoute();
  const { pathname, search } = useLocation();
  React.useEffect(() => {
    const breadcrumbs = getBreadcrumbs(
      matchRoute,
      pathname,
      Object.entries(search).reduce((p, [k, v]) => p + `${k}=${v}`, ''),
      '/',
    );
    setActiveBreadcrumbs(breadcrumbs);
  }, [matchRoute, pathname, search]);
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="supports-backdrop-blur:bg-background/60 sticky top-0 z-10 flex h-16 items-center gap-4 border-b bg-background/80 px-4 backdrop-blur">
          <div className="flex items-center gap-3">
            <SidebarTrigger className="-ml-1" />
            <Separator orientation="vertical" className="h-6" />
            <div className="flex items-center gap-2">
              <img
                alt={`${Config.applicationName} logo`}
                className="size-10 rounded-lg border border-border/60 bg-background object-cover shadow-sm"
                src={Config.logo}
              />
              <div className="flex flex-col leading-tight">
                <span className="text-sm font-semibold">Wealth Management</span>
              </div>
            </div>
          </div>
          <div className="ml-auto flex items-center gap-3" ref={menuRef}>
            <button
              type="button"
              onClick={() => setMenuOpen((open) => !open)}
              className="focus-visible:ring-ring/60 bg-muted text-muted-foreground flex size-10 items-center justify-center rounded-full border border-border/60 font-semibold shadow-sm outline-none transition hover:bg-muted/80 focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-background cursor-pointer"
              aria-label="Open user menu"
              aria-expanded={menuOpen}
            >
              {(user?.profile?.['cognito:username'] as string)
                ?.charAt?.(0)
                ?.toUpperCase?.()}
            </button>
            {menuOpen && (
              <div className="bg-popover text-popover-foreground absolute right-4 top-14 w-36 overflow-hidden rounded-md border shadow-md">
                <div className="px-3 py-2 text-sm font-semibold">
                  Hi, {user?.profile?.['cognito:username'] as any}!
                </div>
                <div className="bg-border/70 h-px w-full" role="separator" />
                <button
                  type="button"
                  className="hover:bg-muted w-full px-3 py-2 text-left text-sm cursor-pointer"
                  onClick={() => {
                    setMenuOpen(false);
                    removeUser();
                    signoutRedirect({
                      post_logout_redirect_uri: window.location.origin,
                      extraQueryParams: {
                        redirect_uri: window.location.origin,
                        response_type: 'code',
                      },
                    });
                    clearStaleState();
                  }}
                >
                  Sign out
                </button>
              </div>
            )}
          </div>
        </header>
        <div className="flex flex-1 flex-col gap-6 p-6 pt-4">
          <Breadcrumb>
            <BreadcrumbList>
              {activeBreadcrumbs.map((crumb, index) => (
                <React.Fragment key={crumb.href || index}>
                  <BreadcrumbItem>
                    {index === activeBreadcrumbs.length - 1 ? (
                      <BreadcrumbPage>{crumb.text}</BreadcrumbPage>
                    ) : (
                      <BreadcrumbLink asChild>
                        <Link to={crumb.href}>{crumb.text}</Link>
                      </BreadcrumbLink>
                    )}
                  </BreadcrumbItem>
                  {index < activeBreadcrumbs.length - 1 && (
                    <BreadcrumbSeparator />
                  )}
                </React.Fragment>
              ))}
            </BreadcrumbList>
          </Breadcrumb>
          {children}
        </div>
      </SidebarInset>
      <ImprovedChatWidget />
    </SidebarProvider>
  );
};

export default AppLayout;
