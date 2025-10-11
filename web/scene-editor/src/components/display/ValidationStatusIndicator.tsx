import React from "react";

import { Badge, type BadgeProps } from "./Badge";
import type { ValidationState } from "../../state";

type ClassValue = string | false | null | undefined;

const classNames = (...values: ClassValue[]): string =>
  values.filter(Boolean).join(" ");

const iconClassName = "h-3.5 w-3.5";

const ValidIcon: React.FC = () => (
  <svg
    viewBox="0 0 20 20"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    className={iconClassName}
    aria-hidden
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M8.5 13.5 5.75 10.75 4.5 12l4 4 7-7-1.25-1.25z"
    />
  </svg>
);

const WarningIcon: React.FC = () => (
  <svg
    viewBox="0 0 20 20"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    className={iconClassName}
    aria-hidden
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M10 3.5 3.5 16.5h13L10 3.5z"
    />
    <path strokeLinecap="round" d="M10 8v3.75" />
    <circle cx="10" cy="14" r="0.9" fill="currentColor" stroke="none" />
  </svg>
);

const ErrorIcon: React.FC = () => (
  <svg
    viewBox="0 0 20 20"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    className={iconClassName}
    aria-hidden
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M5.5 5.5 14.5 14.5M14.5 5.5 5.5 14.5"
    />
  </svg>
);

const iconMap: Record<ValidationState, React.ReactNode> = {
  valid: <ValidIcon />,
  warnings: <WarningIcon />,
  errors: <ErrorIcon />,
};

export interface ValidationStatusDescriptor {
  readonly label: string;
  readonly description: string;
  readonly variant: BadgeProps["variant"];
}

export const VALIDATION_STATUS_DESCRIPTORS: Record<
  ValidationState,
  ValidationStatusDescriptor
> = {
  valid: {
    label: "Ready",
    description: "No validation issues detected for this scene.",
    variant: "success",
  },
  warnings: {
    label: "Review",
    description:
      "Validation warnings present. Review analytics before publishing.",
    variant: "warning",
  },
  errors: {
    label: "Needs Fix",
    description:
      "Blocking validation errors detected. Resolve them before publishing.",
    variant: "danger",
  },
};

type BadgeBaseProps = Omit<
  React.ComponentProps<typeof Badge>,
  "variant" | "children" | "leadingIcon"
>;

export interface ValidationStatusIndicatorProps extends BadgeBaseProps {
  readonly status: ValidationState;
  readonly hideLabel?: boolean;
}

export const ValidationStatusIndicator: React.FC<
  ValidationStatusIndicatorProps
> = ({
  status,
  hideLabel = false,
  size = "sm",
  className,
  title,
  "aria-label": ariaLabel,
  ...badgeProps
}) => {
  const descriptor = VALIDATION_STATUS_DESCRIPTORS[status];
  const resolvedTitle = title ?? descriptor.description;
  const resolvedAriaLabel =
    ariaLabel ?? `${descriptor.label} — ${descriptor.description}`;

  return (
    <Badge
      {...badgeProps}
      variant={descriptor.variant}
      size={size}
      leadingIcon={iconMap[status]}
      className={classNames("tracking-normal", hideLabel ? "px-2" : undefined, className)}
      title={resolvedTitle}
      aria-label={resolvedAriaLabel}
    >
      {hideLabel ? <span className="sr-only">{descriptor.label}</span> : descriptor.label}
    </Badge>
  );
};

export default ValidationStatusIndicator;
