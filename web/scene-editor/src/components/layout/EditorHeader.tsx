import type { ReactNode } from "react";
import React from "react";

export interface EditorHeaderProps {
  readonly title: string;
  readonly subtitle?: ReactNode;
  readonly badge?: ReactNode;
  readonly actions?: ReactNode;
}

export const EditorHeader: React.FC<EditorHeaderProps> = ({
  title,
  subtitle,
  badge,
  actions,
}) => {
  return (
    <header className="border-b border-slate-800 bg-gradient-to-br from-editor-panel to-slate-900 px-6 py-8 shadow-lg">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 text-left lg:flex-row lg:items-end">
        <div className="flex flex-1 flex-col gap-4">
          <div className="flex flex-wrap items-center gap-3">
            {badge ? (
              <span className="inline-flex w-fit items-center gap-2 rounded-full bg-editor-accent/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-editor-accent">
                {badge}
              </span>
            ) : null}
            <h1 className="text-3xl font-semibold text-white md:text-4xl">{title}</h1>
          </div>
          {subtitle ? (
            <div className="max-w-3xl text-sm text-slate-300 md:text-base">{subtitle}</div>
          ) : null}
        </div>
        {actions ? (
          <div className="flex items-center gap-3 text-sm text-slate-300">{actions}</div>
        ) : null}
      </div>
    </header>
  );
};

export default EditorHeader;
