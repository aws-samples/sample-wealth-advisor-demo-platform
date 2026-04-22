import { Home, Network } from 'lucide-react';

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from ':wealth-management-portal/common-shadcn/components/ui/sidebar';
import { Link } from '@tanstack/react-router';

import Config from '../config';

export function AppSidebar() {
  // Menu items.
  const navItems = [
    {
      label: 'Home',
      to: '/',
      icon: Home,
    },
    {
      label: 'Graph Search',
      to: '/graph-search',
      icon: Network,
    },
  ];
  return (
    <Sidebar>
      <SidebarContent>
        <SidebarGroup>
          <div className="flex items-center gap-3 px-4 py-3 border-b">
            <img
              alt="Wealth Management logo"
              className="size-10 rounded-lg border border-border/60 bg-background object-cover shadow-sm"
              src={Config.logo}
            />
            <div className="flex flex-col leading-tight">
              <span className="text-sm font-semibold">Wealth Management</span>
            </div>
          </div>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.label}>
                  <SidebarMenuButton asChild>
                    <Link to={item.to} preload="intent">
                      <item.icon />
                      <span>{item.label}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
}
