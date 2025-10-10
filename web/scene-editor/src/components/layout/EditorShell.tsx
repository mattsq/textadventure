import type { ReactNode } from "react";
import React from "react";

export interface EditorShellProps {
  readonly header: ReactNode;
  readonly children: ReactNode;
  readonly sidebar?: ReactNode;
  readonly footer?: ReactNode;
}

export const EditorShell: React.FC<EditorShellProps> = ({
  header,
  sidebar,
  children,
  footer,
}) => {
  return (
    <div className="flex min-h-screen bg-editor-surface text-slate-100">
      {sidebar ? (
        <aside className="hidden w-72 shrink-0 border-r border-slate-800 bg-editor-panel/90 shadow-2xl shadow-slate-950/40 lg:flex">
          <div className="flex w-full flex-col gap-6 overflow-y-auto px-6 py-8">
            {sidebar}
          </div>
        </aside>
      ) : null}
      <div className="flex min-h-screen flex-1 flex-col">
        {header}
        <main className="flex-1 px-6 py-10 lg:px-10">{children}</main>
        {footer ? (
          <footer className="border-t border-slate-800 bg-editor-panel/80 px-6 py-4 text-xs text-slate-500">
            {footer}
          </footer>
        ) : null}
      </div>
    </div>
  );
};

export default EditorShell;
