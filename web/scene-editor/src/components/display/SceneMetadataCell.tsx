import React from "react";

export interface SceneMetadataCellProps {
  readonly id: string;
  readonly description: string;
  readonly choiceCount: number;
  readonly transitionCount: number;
}

const metadataChipClassName =
  "inline-flex items-center gap-1 rounded-md border border-slate-700/70 bg-slate-900/70 px-2 py-0.5 text-[11px] font-medium text-slate-200";

const formatCountLabel = (
  count: number,
  singular: string,
  plural: string,
): string => `${count} ${count === 1 ? singular : plural}`;

export const SceneMetadataCell: React.FC<SceneMetadataCellProps> = ({
  id,
  description,
  choiceCount,
  transitionCount,
}) => {
  const normalizedDescription = description.trim()
    ? description.trim()
    : "No description provided yet.";

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-slate-50 md:text-base">{id}</span>
        <div className="flex flex-wrap gap-1.5">
          <span className={metadataChipClassName}>
            <span
              className="h-1.5 w-1.5 rounded-full bg-sky-400"
              aria-hidden
            />
            {formatCountLabel(choiceCount, "choice", "choices")}
          </span>
          <span className={metadataChipClassName}>
            <span
              className="h-1.5 w-1.5 rounded-full bg-violet-400"
              aria-hidden
            />
            {formatCountLabel(transitionCount, "transition", "transitions")}
          </span>
        </div>
      </div>
      <p
        className="max-w-prose text-xs leading-relaxed text-slate-400 md:text-sm"
        title={normalizedDescription}
      >
        {normalizedDescription}
      </p>
    </div>
  );
};

export default SceneMetadataCell;
