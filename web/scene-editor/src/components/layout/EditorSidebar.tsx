import type { ReactNode } from "react";
import React from "react";

export interface EditorSidebarSection {
  readonly title: string;
  readonly content: ReactNode;
  readonly footer?: ReactNode;
}

export interface EditorSidebarProps {
  readonly title?: string;
  readonly actions?: ReactNode;
  readonly sections?: readonly EditorSidebarSection[];
  readonly footer?: ReactNode;
  readonly children?: ReactNode;
}

export const EditorSidebar: React.FC<EditorSidebarProps> = ({
  title,
  actions,
  sections,
  footer,
  children,
}) => {
  return (
    <div className="flex h-full flex-col gap-6 text-sm text-slate-300">
      {(title || actions) && (
        <div className="flex items-center justify-between gap-3">
          {title ? <h2 className="text-base font-semibold text-white">{title}</h2> : <span />}
          {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
        </div>
      )}
      {sections?.map((section) => (
        <section key={section.title} className="space-y-3 rounded-lg border border-slate-800 bg-slate-900/50 p-4 shadow-lg shadow-slate-950/20">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            {section.title}
          </h3>
          <div className="text-sm text-slate-300">{section.content}</div>
          {section.footer ? (
            <div className="text-xs text-slate-500">{section.footer}</div>
          ) : null}
        </section>
      ))}
      {children}
      {footer ? <div className="mt-auto text-xs text-slate-500">{footer}</div> : null}
    </div>
  );
};

export default EditorSidebar;
