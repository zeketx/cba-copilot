/*
 * Copyright (c) 2026 Shane Levine
 * Beautiful UI, MIT License. https://www.beautifului.dev/license
 */

import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { createPortal } from "react-dom";
import GlideMenu from "@/components/beautifui/GlideMenu";

/* ─────────────────────────────────────────────────────────
 * SIDEBAR NAV
 * Compact workspace switcher, primary navigation, searchable
 * chat history, and a collapse that preserves icon alignment.
 * ───────────────────────────────────────────────────────── */

const WORKSPACE = { key: "cba", name: "CBA Copilot", monogram: "C" };

export type SidebarRecent = {
  id: string;
  label: string;
  prompt?: string;
};

type SidebarNavProps = {
  activeId?: string | null;
  className?: string;
  fill?: boolean;
  onNewChat?: () => void;
  onPick?: (id: string, label: string, prompt?: string) => void;
  activeNav?: string;
  onNavigate?: (key: string) => void;
  footerLabel?: string;
  footerIcon?: ReactNode;
  onFooterClick?: () => void;
  recents: SidebarRecent[];
  userEmail?: string;
  onSignOut?: () => void;
  onRename?: (id: string, title: string) => void;
  onDelete?: (id: string) => void;
  variant?: string;
};

const SIDEBAR_MOTION = {
  expandedWidth: 224,
  collapsedWidth: 52,
  duration: 280,
  copyDuration: 180,
  copyOffset: 8,
  easing: "cubic-bezier(0.16, 1, 0.3, 1)",
};

/* ─────────────────────────────────────────────────────────
 * CHAT SEARCH STORYBOARD
 *
 *   0ms   search is triggered; Chats label begins fading
 *   0ms   field grows right → left from the search control
 * 180ms   field fills the row; cursor is focused and ready
 * ───────────────────────────────────────────────────────── */
const CHAT_SEARCH_MOTION = {
  duration: 180,
  closedWidth: 28,
  easing: "cubic-bezier(0.16, 1, 0.3, 1)",
};

function StrokeIcon({
  size,
  className,
  children,
}: {
  size: number;
  className?: string;
  children: ReactNode;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

function IconBook({ size }: { size: number }) {
  return (
    <StrokeIcon size={size}>
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M4 4.5A2.5 2.5 0 0 1 6.5 7H20v13H6.5A2.5 2.5 0 0 0 4 22.5z" />
    </StrokeIcon>
  );
}

function IconCheck({ size }: { size: number }) {
  return (
    <StrokeIcon size={size}>
      <path d="M5 12.5 9.5 17 19 7.5" />
    </StrokeIcon>
  );
}

function IconChevronDown({ size }: { size: number }) {
  return (
    <StrokeIcon size={size}>
      <path d="M6 9l6 6 6-6" />
    </StrokeIcon>
  );
}

function IconClose({ size }: { size: number }) {
  return (
    <StrokeIcon size={size}>
      <path d="M6 6l12 12M18 6 6 18" />
    </StrokeIcon>
  );
}

function IconCollapse({ size, className }: { size: number; className?: string }) {
  return (
    <StrokeIcon size={size} className={className}>
      <path d="M4 5h10v14H4z" />
      <path d="M20 12H11" />
      <path d="M14 8l-4 4 4 4" />
    </StrokeIcon>
  );
}

function IconDots({ size }: { size: number }) {
  return (
    <StrokeIcon size={size}>
      <path d="M6 12h.01M12 12h.01M18 12h.01" />
    </StrokeIcon>
  );
}

function IconLogo({ size }: { size: number }) {
  return (
    <StrokeIcon size={size}>
      <path d="M7 4h8l4 4v12H7z" />
      <path d="M15 4v4h4" />
      <path d="M10 12h6M10 16h4" />
    </StrokeIcon>
  );
}

function IconNewChat({ size }: { size: number }) {
  return (
    <StrokeIcon size={size}>
      <path d="M4 20l3.2-1.2L20 6.1 16.9 3 4.1 15.8z" />
      <path d="M13.8 5.1 17.9 9.2" />
    </StrokeIcon>
  );
}

function IconRename({ size }: { size: number }) {
  return (
    <StrokeIcon size={size}>
      <path d="M4 20h4l11-11-4-4L4 16z" />
      <path d="M13 7l4 4" />
    </StrokeIcon>
  );
}

function IconSearch({ size }: { size: number }) {
  return (
    <StrokeIcon size={size}>
      <path d="M10.5 18a7.5 7.5 0 1 1 0-15 7.5 7.5 0 0 1 0 15z" />
      <path d="M16 16l5 5" />
    </StrokeIcon>
  );
}

function IconSignOut({ size }: { size: number }) {
  return (
    <StrokeIcon size={size}>
      <path d="M10 5H5v14h5" />
      <path d="M12 12h8" />
      <path d="M16 8l4 4-4 4" />
    </StrokeIcon>
  );
}

function IconTrash({ size }: { size: number }) {
  return (
    <StrokeIcon size={size}>
      <path d="M5 7h14" />
      <path d="M10 7V5h4v2" />
      <path d="M8 7l.8 12h6.4L16 7" />
    </StrokeIcon>
  );
}

function chatLabel(label: string): string {
  return label.trim() === "" ? "New chat" : label;
}

function GlideGroup({ children }: { children: ReactNode }) {
  return (
    <GlideMenu
      rowSelector="[data-row]"
      highlightClassName="sidebar-glide-highlight rounded-[7px] bg-hover-2"
      className="group/glide flex flex-col gap-px"
    >
      {children}
    </GlideMenu>
  );
}

function RailButton({
  icon,
  label,
  active = false,
  count,
  onClick,
}: {
  icon: ReactNode;
  label: string;
  active?: boolean;
  count?: string;
  onClick?: () => void;
}) {
  return (
    <button
      data-row
      type="button"
      onClick={onClick}
      className={`sidebar-row relative z-10 mx-2 flex h-8 items-center rounded-[8px] px-2 text-left
        transition-[width,background-color,color,transform] duration-150 active:scale-[0.98]
        ${active ? "bg-hover-2 group-hover/glide:bg-transparent" : ""}`}
    >
      <span className={`flex size-5 shrink-0 items-center justify-center ${active ? "text-ink" : "text-ink-2"}`}>
        {icon}
      </span>
      <span className={`sidebar-copy ml-1.5 min-w-0 flex-1 truncate text-[14px] font-medium ${active ? "text-ink" : "text-ink-2"}`}>
        {label}
      </span>
      {count ? (
        <span className="sidebar-copy mr-2 shrink-0 text-[12px] font-medium text-ink-3 tabular-nums">
          {count}
        </span>
      ) : null}
    </button>
  );
}

function WorkspaceMenu({
  position,
  email,
  onClose,
  onSignOut,
}: {
  position: { top: number; left: number };
  email?: string;
  onClose: () => void;
  onSignOut?: () => void;
}) {
  return createPortal(
    <div
      data-workspace-menu
      className="fixed z-50 w-64 rounded-[14px] bg-surface p-1.5 shadow-overlay"
      style={{
        top: position.top,
        left: position.left,
        animation: "pop-in 180ms cubic-bezier(0.23,1,0.32,1) both",
        transformOrigin: "top left",
      }}
    >
      <GlideMenu className="flex flex-col gap-px" highlightClassName="inset-x-0 rounded-[8px] bg-hover-2">
        <button
          data-menu-row
          type="button"
          onClick={onClose}
          className="relative z-10 flex h-10 w-full items-center gap-1.5 rounded-[8px] px-2 text-left"
        >
          <span className="flex size-6 shrink-0 items-center justify-center rounded-[7px] bg-ink text-[11px] font-semibold text-surface">
            {WORKSPACE.monogram}
          </span>
          <span className="min-w-0 flex-1 truncate text-[13.5px] font-medium text-ink">
            {email?.trim() ? email : WORKSPACE.name}
          </span>
          <span className="shrink-0 text-ink">
            <IconCheck size={18} />
          </span>
        </button>
        <div className="my-1 h-px bg-line" />
        <button
          data-menu-row
          type="button"
          onClick={() => {
            onSignOut?.();
            onClose();
          }}
          className="relative z-10 flex h-9 w-full items-center gap-1.5 rounded-[8px] px-2 text-left"
        >
          <span className="flex size-5 shrink-0 items-center justify-center text-ink-2">
            <IconSignOut size={16} />
          </span>
          <span className="min-w-0 flex-1 truncate text-[13.5px] text-ink">Sign out</span>
        </button>
      </GlideMenu>
    </div>,
    document.body,
  );
}

function RecentMenu({
  position,
  confirmDelete,
  onRename,
  onDelete,
  onConfirmDelete,
}: {
  position: { top: number; left: number };
  confirmDelete: boolean;
  onRename: () => void;
  onDelete: () => void;
  onConfirmDelete: () => void;
}) {
  return createPortal(
    <div
      data-recent-menu
      className="fixed z-50 w-52 rounded-[14px] bg-surface p-1.5 shadow-overlay"
      style={{
        top: position.top,
        left: position.left,
        animation: "pop-in 180ms cubic-bezier(0.23,1,0.32,1) both",
        transformOrigin: "top left",
      }}
    >
      <GlideMenu className="flex flex-col gap-px" highlightClassName="inset-x-0 rounded-[8px] bg-hover-2">
        {confirmDelete ? (
          <>
            <div className="relative z-10 flex h-9 w-full items-center rounded-[8px] px-2 text-[13.5px] font-medium text-ink">
              Delete chat
            </div>
            <button
              data-menu-row
              type="button"
              onClick={onConfirmDelete}
              className="relative z-10 flex h-9 w-full items-center gap-1.5 rounded-[8px] px-2 text-left"
            >
              <span className="flex size-5 shrink-0 items-center justify-center text-ink-2">
                <IconTrash size={16} />
              </span>
              <span className="min-w-0 flex-1 truncate text-[13.5px] text-ink">Confirm delete</span>
            </button>
          </>
        ) : (
          <>
            <button
              data-menu-row
              type="button"
              onClick={onRename}
              className="relative z-10 flex h-9 w-full items-center gap-1.5 rounded-[8px] px-2 text-left"
            >
              <span className="flex size-5 shrink-0 items-center justify-center text-ink-2">
                <IconRename size={16} />
              </span>
              <span className="min-w-0 flex-1 truncate text-[13.5px] text-ink">Rename</span>
            </button>
            <button
              data-menu-row
              type="button"
              onClick={onDelete}
              className="relative z-10 flex h-9 w-full items-center gap-1.5 rounded-[8px] px-2 text-left"
            >
              <span className="flex size-5 shrink-0 items-center justify-center text-ink-2">
                <IconTrash size={16} />
              </span>
              <span className="min-w-0 flex-1 truncate text-[13.5px] text-ink">Delete</span>
            </button>
          </>
        )}
      </GlideMenu>
    </div>,
    document.body,
  );
}

export default function SidebarNav({
  activeId = null,
  className = "",
  fill = false,
  onNewChat,
  onPick,
  activeNav,
  onNavigate,
  footerLabel,
  footerIcon,
  onFooterClick,
  recents,
  userEmail,
  onSignOut,
  onRename,
  onDelete,
}: SidebarNavProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [internalNav, setInternalNav] = useState("chats");
  const currentNav = activeNav ?? internalNav;
  const selectNav = (key: string) => {
    setInternalNav(key);
    onNavigate?.(key);
  };
  const [workspaceOpen, setWorkspaceOpen] = useState(false);
  const [workspacePosition, setWorkspacePosition] = useState({ top: 0, left: 0 });
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [rowMenu, setRowMenu] = useState<{ id: string; top: number; left: number } | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState("");
  const workspaceButtonRef = useRef<HTMLButtonElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const renameRef = useRef<HTMLInputElement>(null);

  const visibleRecents = recents.filter((item) =>
    chatLabel(item.label).toLowerCase().includes(query.trim().toLowerCase()),
  );

  useEffect(() => {
    if (!workspaceOpen && rowMenu === null) return;
    const close = (event: PointerEvent) => {
      const target = event.target as Element;
      if (
        !target.closest("[data-workspace-trigger]") &&
        !target.closest("[data-workspace-menu]")
      ) {
        setWorkspaceOpen(false);
      }
      if (!target.closest("[data-recent-trigger]") && !target.closest("[data-recent-menu]")) {
        setRowMenu(null);
        setConfirmDelete(false);
      }
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setWorkspaceOpen(false);
      setRowMenu(null);
      setConfirmDelete(false);
    };
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", onKey);
    };
  }, [workspaceOpen, rowMenu]);

  useEffect(() => {
    if (searchOpen) searchRef.current?.focus();
  }, [searchOpen]);

  useEffect(() => {
    if (renamingId !== null) renameRef.current?.focus();
  }, [renamingId]);

  const collapse = () => {
    setCollapsed(true);
    setWorkspaceOpen(false);
    setSearchOpen(false);
    setQuery("");
    setRowMenu(null);
    setConfirmDelete(false);
    setRenamingId(null);
  };

  const saveRename = (id: string) => {
    const title = renameDraft.trim();
    if (title === "") return;
    onRename?.(id, title);
    setRenamingId(null);
    setRenameDraft("");
  };

  return (
    <aside
      data-sidebar-collapsed={collapsed}
      aria-label="Workspace navigation"
      className={`relative flex shrink-0 overflow-hidden transition-[width] ${fill ? "h-full" : "h-[600px]"} ${className}`}
      style={
        {
          width: collapsed ? SIDEBAR_MOTION.collapsedWidth : SIDEBAR_MOTION.expandedWidth,
          transitionDuration: `${SIDEBAR_MOTION.duration}ms`,
          transitionTimingFunction: SIDEBAR_MOTION.easing,
          "--sidebar-copy-duration": `${SIDEBAR_MOTION.copyDuration}ms`,
          "--sidebar-copy-offset": `${SIDEBAR_MOTION.copyOffset}px`,
          "--sidebar-easing": SIDEBAR_MOTION.easing,
        } as CSSProperties
      }
    >
      <div className="flex min-h-0 w-[224px] shrink-0 flex-col">
        <div className="relative mb-2.5 h-10 shrink-0">
          <button
            ref={workspaceButtonRef}
            data-workspace-trigger
            type="button"
            aria-expanded={workspaceOpen}
            aria-hidden={collapsed}
            tabIndex={collapsed ? -1 : 0}
            onClick={() => {
              if (!workspaceOpen && workspaceButtonRef.current) {
                const rect = workspaceButtonRef.current.getBoundingClientRect();
                setWorkspacePosition({ top: rect.bottom + 6, left: rect.left });
              }
              setWorkspaceOpen((open) => !open);
            }}
            className="sidebar-workspace-control absolute top-1 left-2 flex h-8 w-[164px] items-center rounded-[8px] px-2 text-left transition-[background-color,transform] duration-100 hover:bg-hover-2 active:scale-[0.99]"
          >
            <span className="sidebar-logo flex size-5 shrink-0 items-center justify-center text-ink">
              <IconLogo size={18} />
            </span>
            <span className="sidebar-copy ml-1.5 min-w-0 flex-1 truncate text-[14px] font-medium text-ink-2">
              {WORKSPACE.name}
            </span>
            <span className="sidebar-copy ml-1 flex shrink-0 text-ink-3">
              <IconChevronDown size={16} />
            </span>
          </button>

          {workspaceOpen ? (
            <WorkspaceMenu
              position={workspacePosition}
              email={userEmail}
              onClose={() => setWorkspaceOpen(false)}
              onSignOut={onSignOut}
            />
          ) : null}

          <button
            type="button"
            aria-label="Collapse sidebar"
            aria-hidden={collapsed}
            tabIndex={collapsed ? -1 : 0}
            onClick={collapse}
            className="sidebar-collapse-control absolute top-1 right-2 flex size-8 items-center justify-center rounded-[8px] text-ink-3 transition-[opacity,background-color,color] duration-150 hover:bg-hover-2 hover:text-ink"
          >
            <IconCollapse size={18} />
          </button>
          <button
            type="button"
            aria-label="Expand sidebar"
            aria-hidden={!collapsed}
            tabIndex={collapsed ? 0 : -1}
            onClick={() => setCollapsed(false)}
            className="sidebar-expand-control absolute top-0.5 left-2 flex size-9 items-center justify-center rounded-[8px] text-ink-3 transition-[opacity,background-color,color] duration-150 hover:bg-hover-2 hover:text-ink"
          >
            <IconCollapse size={18} className="rotate-180" />
          </button>
        </div>

        <GlideGroup>
          <RailButton
            icon={<IconNewChat size={18} />}
            label="New chat"
            onClick={() => {
              selectNav("chats");
              onNewChat?.();
            }}
          />
          <RailButton
            icon={<IconBook size={18} />}
            label="Definitions"
            active={currentNav === "definitions"}
            onClick={() => selectNav("definitions")}
          />
        </GlideGroup>

        <div className="mt-3 min-h-0 flex-1 overflow-y-auto">
          <div className="sidebar-copy relative mx-2 mb-1 h-8">
            <div
              aria-hidden={searchOpen}
              className={`absolute inset-0 flex items-center gap-1.5 px-2 text-[12.5px] font-medium text-ink-3 transition-[opacity,transform] ${searchOpen ? "pointer-events-none -translate-x-1 opacity-0" : "translate-x-0 opacity-100"}`}
              style={{
                transitionDuration: `${CHAT_SEARCH_MOTION.duration}ms`,
                transitionTimingFunction: CHAT_SEARCH_MOTION.easing,
              }}
            >
              <IconChevronDown size={16} />
              <span>Chats</span>
            </div>

            <button
              type="button"
              aria-label="Search chats"
              aria-expanded={searchOpen}
              onClick={() => setSearchOpen(true)}
              className={`absolute top-0 right-0 z-10 flex size-8 items-center justify-center rounded-[8px] text-ink-3 transition-[opacity,background-color,color,transform] hover:bg-hover-2 hover:text-ink active:scale-[0.96] ${searchOpen ? "pointer-events-none opacity-0" : "opacity-100"}`}
              style={{ transitionDuration: `${CHAT_SEARCH_MOTION.duration}ms` }}
            >
              <IconSearch size={16} />
            </button>

            <div
              className={`absolute top-0 right-0 z-20 flex h-8 items-center overflow-hidden rounded-[8px] bg-field text-ink-3 shadow-hairline transition-[width,opacity] focus-within:text-ink-2 ${searchOpen ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"}`}
              style={{
                width: searchOpen ? "100%" : CHAT_SEARCH_MOTION.closedWidth,
                transitionDuration: `${CHAT_SEARCH_MOTION.duration}ms`,
                transitionTimingFunction: CHAT_SEARCH_MOTION.easing,
              }}
            >
              <span className="ml-2 flex shrink-0 items-center justify-center">
                <IconSearch size={15} />
              </span>
              <input
                ref={searchRef}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Escape") {
                    setSearchOpen(false);
                    setQuery("");
                  }
                }}
                placeholder="Search chats"
                aria-label="Search chat history"
                className="ml-1.5 min-w-0 flex-1 bg-transparent text-[13px] font-medium text-ink outline-none placeholder:text-ink-3"
              />
              <button
                type="button"
                aria-label="Close chat search"
                onClick={() => {
                  setSearchOpen(false);
                  setQuery("");
                }}
                className="flex size-8 shrink-0 items-center justify-center rounded-[8px] text-ink-3 transition-[background-color,color,transform] duration-150 hover:bg-hover-2 hover:text-ink active:scale-[0.96]"
              >
                <IconClose size={16} />
              </button>
            </div>
          </div>

          <GlideGroup>
            {visibleRecents.map((item) => {
              const active = item.id === activeId;
              const renaming = renamingId === item.id;
              const shown = chatLabel(item.label);
              return (
                <div
                  key={item.id}
                  data-row
                  className={`sidebar-row group/recent relative z-10 mx-2 flex h-8 items-center rounded-[8px] px-2 text-left transition-[width,background-color,color,transform] duration-150 ${
                    active ? "bg-hover-2 group-hover/glide:bg-transparent" : ""
                  }`}
                >
                  {renaming ? (
                    <input
                      ref={renameRef}
                      value={renameDraft}
                      onChange={(event) => setRenameDraft(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          saveRename(item.id);
                        }
                        if (event.key === "Escape") {
                          event.preventDefault();
                          setRenamingId(null);
                          setRenameDraft("");
                        }
                      }}
                      onBlur={() => {
                        setRenamingId(null);
                        setRenameDraft("");
                      }}
                      aria-label="Rename chat"
                      className="min-w-0 flex-1 bg-transparent text-[13px] font-medium text-ink outline-none placeholder:text-ink-3"
                    />
                  ) : (
                    <>
                      <button
                        type="button"
                        title={shown}
                        onClick={() => {
                          selectNav("chats");
                          onPick?.(item.id, item.label, item.prompt);
                        }}
                        className="flex min-w-0 flex-1 items-center text-left active:scale-[0.98]"
                      >
                        <span
                          className={`sidebar-copy min-w-0 flex-1 truncate text-[14px] font-medium ${active ? "text-ink" : "text-ink-2"}`}
                        >
                          {shown}
                        </span>
                      </button>
                      <button
                        data-recent-trigger
                        type="button"
                        aria-label={`Actions for ${shown}`}
                        aria-expanded={rowMenu?.id === item.id}
                        onClick={(event) => {
                          event.stopPropagation();
                          const rect = event.currentTarget.getBoundingClientRect();
                          setConfirmDelete(false);
                          setRowMenu((current) =>
                            current?.id === item.id
                              ? null
                              : { id: item.id, top: rect.bottom + 6, left: rect.right - 208 },
                          );
                        }}
                        className="flex size-6 shrink-0 items-center justify-center rounded-[6px] text-ink-3 opacity-0 transition-[opacity,background-color,color] group-hover/recent:opacity-100 group-focus-within/recent:opacity-100 hover:bg-hover-2 hover:text-ink"
                      >
                        <IconDots size={16} />
                      </button>
                    </>
                  )}
                </div>
              );
            })}
            {query && visibleRecents.length === 0 ? (
              <div className="sidebar-copy mx-2 px-2 py-2 text-[12.5px] text-ink-3">No chats found</div>
            ) : null}
          </GlideGroup>
        </div>

        {footerLabel ? (
          <div className="sidebar-copy mx-2 mt-3 w-[208px] border-t border-line pt-3">
            <button
              type="button"
              onClick={onFooterClick ?? onNewChat}
              className="flex h-8 w-full items-center justify-center gap-1.5 rounded-control bg-hover-2 text-[12.5px] font-medium text-ink transition-[background-color,transform] duration-150 hover:bg-line-strong active:scale-[0.98]"
            >
              {footerIcon}
              {footerLabel}
            </button>
          </div>
        ) : null}
      </div>
      {rowMenu ? (
        <RecentMenu
          position={{ top: rowMenu.top, left: rowMenu.left }}
          confirmDelete={confirmDelete}
          onRename={() => {
            const target = recents.find((item) => item.id === rowMenu.id);
            setRenameDraft(target?.label ?? "");
            setRenamingId(rowMenu.id);
            setRowMenu(null);
            setConfirmDelete(false);
          }}
          onDelete={() => setConfirmDelete(true)}
          onConfirmDelete={() => {
            onDelete?.(rowMenu.id);
            setRowMenu(null);
            setConfirmDelete(false);
          }}
        />
      ) : null}
    </aside>
  );
}
