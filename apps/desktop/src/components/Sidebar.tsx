import React, { useEffect } from "react";
import {
  Activity,
  Command,
  Cpu,
  Eye,
  GitBranch,
  GraduationCap,
  Home,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  TerminalSquare,
  X,
} from "lucide-react";
import { BrandMark } from "./BrandMark";

export type SectionId =
  | "home"
  | "operator"
  | "live"
  | "workflows"
  | "teach"
  | "activity"
  | "models"
  | "settings";

interface NavItem {
  id: SectionId;
  label: string;
  icon: React.ComponentType<{ size?: number; "aria-hidden"?: boolean }>;
  badge?: number;
}

interface SidebarProps {
  active: SectionId;
  onSelect: (id: SectionId) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
  onOpenPalette: () => void;
  activeTasksCount: number;
  pendingApprovalsCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  active,
  onSelect,
  collapsed,
  onToggleCollapse,
  mobileOpen,
  onCloseMobile,
  onOpenPalette,
  activeTasksCount,
  pendingApprovalsCount,
}) => {
  useEffect(() => {
    if (!mobileOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCloseMobile();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mobileOpen, onCloseMobile]);

  const workspaceNav: NavItem[] = [
    { id: "home", label: "Home", icon: Home },
    {
      id: "operator",
      label: "Operator",
      icon: TerminalSquare,
      badge: pendingApprovalsCount || activeTasksCount || undefined,
    },
    { id: "live", label: "Live Workspace", icon: Eye },
  ];

  const automationNav: NavItem[] = [
    { id: "workflows", label: "Workflow Studio", icon: GitBranch },
    { id: "teach", label: "Teach Mode", icon: GraduationCap },
    { id: "activity", label: "Activity", icon: Activity },
  ];

  const systemNav: NavItem[] = [
    { id: "models", label: "Models", icon: Cpu },
    { id: "settings", label: "Settings", icon: Settings },
  ];

  const handleSelect = (id: SectionId) => {
    onSelect(id);
    onCloseMobile();
  };

  const renderGroup = (title: string, items: NavItem[]) => (
    <div className="nav-group" role="group" aria-label={title}>
      {!collapsed && <div className="nav-group-label">{title}</div>}
      {items.map((item) => {
        const Icon = item.icon;
        const isCurrent = active === item.id;
        return (
          <button
            key={item.id}
            type="button"
            className="nav-item"
            aria-current={isCurrent ? "page" : undefined}
            aria-label={collapsed ? item.label : undefined}
            title={collapsed ? item.label : undefined}
            onClick={() => handleSelect(item.id)}
          >
            <Icon size={17} aria-hidden={true} />
            {!collapsed && <span className="nav-item-label">{item.label}</span>}
            {!collapsed && item.badge ? (
              <span className="nav-count tabular" aria-label={`${item.badge} active`}>
                {item.badge}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );

  return (
    <>
      <div
        className="drawer-backdrop"
        data-open={mobileOpen ? "true" : "false"}
        onClick={onCloseMobile}
        aria-hidden="true"
      />
      <aside
        className="sidebar"
        data-mobile-open={mobileOpen ? "true" : "false"}
        aria-label="Primary application navigation"
      >
        <div className="sidebar-drag-strip" data-tauri-drag-region="true" aria-hidden="true" />
        <div className="sidebar-header">
          <div className="brand-lockup">
            <BrandMark size={28} />
            {!collapsed && <span className="brand-wordmark">OmniDesk</span>}
          </div>
          {mobileOpen ? (
            <button
              type="button"
              className="btn btn-ghost btn-icon"
              aria-label="Close navigation menu"
              onClick={onCloseMobile}
            >
              <X size={17} aria-hidden="true" />
            </button>
          ) : (
            <button
              type="button"
              className="btn btn-ghost btn-icon"
              aria-expanded={!collapsed}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              onClick={onToggleCollapse}
            >
              {collapsed ? (
                <PanelLeftOpen size={17} aria-hidden="true" />
              ) : (
                <PanelLeftClose size={17} aria-hidden="true" />
              )}
            </button>
          )}
        </div>

        <nav aria-label="Workspace sections" className="list-stack" style={{ gap: 14 }}>
          {renderGroup("Operate", workspaceNav)}
          {renderGroup("Automate", automationNav)}
          {renderGroup("System", systemNav)}
        </nav>

        <div className="sidebar-footer">
          <button
            type="button"
            className="btn"
            style={{
              justifyContent: collapsed ? "center" : "space-between",
              width: "100%",
              paddingInline: collapsed ? 0 : 10,
              fontSize: 13,
            }}
            aria-label="Open command palette"
            onClick={() => {
              onCloseMobile();
              onOpenPalette();
            }}
          >
            <span className="flex-row" style={{ gap: 7, minWidth: 0 }}>
              <Command size={14} aria-hidden="true" />
              {!collapsed && <span className="truncate">Command Palette</span>}
            </span>
            {!collapsed && <kbd className="kbd-cap">Cmd K</kbd>}
          </button>
        </div>
      </aside>
    </>
  );
};
