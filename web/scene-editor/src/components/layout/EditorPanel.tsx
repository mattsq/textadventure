import type { ReactNode } from "react";
import React from "react";

export interface EditorPanelProps {
  readonly title?: ReactNode;
  readonly description?: ReactNode;
  readonly actions?: ReactNode;
  readonly footer?: ReactNode;
  readonly children: ReactNode;
  readonly variant?: "default" | "subtle";
}

const panelVariants: Record<NonNullable<EditorPanelProps["variant"]>, string> = {
  default:
    "rounded-xl border border-slate-800 bg-editor-panel/70 p-6 shadow-xl shadow-slate-950/40 backdrop-blur",
  subtle:
    "rounded-lg border border-slate-800/80 bg-slate-900/50 p-5 shadow-lg shadow-slate-950/20",
};

export const EditorPanel: React.FC<EditorPanelProps> = ({
  title,
  description,
  actions,
  footer,
  children,
  variant = "default",
}) => {
  return (
    <section className={panelVariants[variant]}>
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div className="space-y-2">
          {title ? (
            <h2 className="text-xl font-semibold text-white md:text-2xl">{title}</h2>
          ) : null}
          {description ? (
            <div className="text-sm leading-relaxed text-slate-300 md:text-base">{description}</div>
          ) : null}
        </div>
        {actions ? (
          <div className="flex flex-shrink-0 items-center gap-2 text-sm text-slate-300">{actions}</div>
        ) : null}
      </div>
      <div className="mt-6 space-y-4 text-sm text-slate-200 md:text-base">{children}</div>
      {footer ? (
        <div className="mt-6 border-t border-slate-800/80 pt-4 text-xs text-slate-500">{footer}</div>
      ) : null}
    </section>
  );
};

export default EditorPanel;
