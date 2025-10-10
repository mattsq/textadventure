import React, { forwardRef, useId } from "react";

type ClassValue = string | false | null | undefined;

const classNames = (...values: ClassValue[]): string =>
  values.filter(Boolean).join(" ");

export interface BaseFieldProps {
  readonly label: React.ReactNode;
  readonly description?: React.ReactNode;
  readonly error?: React.ReactNode;
  readonly className?: string;
  readonly inputClassName?: string;
}

interface FieldWrapperProps extends BaseFieldProps {
  readonly id: string;
  readonly descriptionId?: string;
  readonly errorId?: string;
  readonly children: React.ReactNode;
  readonly required?: boolean;
}

const FieldWrapper: React.FC<FieldWrapperProps> = ({
  id,
  label,
  description,
  descriptionId,
  error,
  errorId,
  required,
  className,
  children,
}) => {
  return (
    <div className={classNames("flex flex-col gap-2", className)}>
      <div className="flex flex-col gap-1">
        <label htmlFor={id} className="text-sm font-medium text-slate-200">
          {label}
          {required ? <span className="ml-1 text-red-400">*</span> : null}
        </label>
        {description ? (
          <p id={descriptionId} className="text-xs text-slate-400">
            {description}
          </p>
        ) : null}
      </div>
      {children}
      {error ? (
        <p id={errorId} className="text-xs font-medium text-red-400">
          {error}
        </p>
      ) : null}
    </div>
  );
};

const baseControlClasses =
  "w-full rounded-lg border px-4 py-2 text-sm shadow-inner shadow-slate-950/30 transition focus:outline-none focus:ring-2";
const defaultControlClasses =
  "border-slate-700/80 bg-slate-900/60 text-slate-100 placeholder:text-slate-500 focus:border-indigo-400 focus:ring-indigo-500/40";
const errorControlClasses =
  "border-red-500/80 bg-slate-900/60 text-slate-100 placeholder:text-slate-500 focus:border-red-400 focus:ring-red-500/40";

const buildControlClassName = (
  hasError: boolean,
  inputClassName?: string,
): string =>
  classNames(
    baseControlClasses,
    hasError ? errorControlClasses : defaultControlClasses,
    inputClassName,
  );

export interface TextFieldProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "size" | "className">,
    BaseFieldProps {}

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(
  (
    {
      label,
      description,
      error,
      required,
      className,
      inputClassName,
      id,
      type = "text",
      ...props
    },
    ref,
  ) => {
    const fallbackId = useId();
    const fieldId = id ?? fallbackId;
    const descriptionId = description ? `${fieldId}-description` : undefined;
    const errorId = error ? `${fieldId}-error` : undefined;
    const describedBy = [descriptionId, errorId].filter(Boolean).join(" ") || undefined;

    return (
      <FieldWrapper
        id={fieldId}
        label={label}
        description={description}
        descriptionId={descriptionId}
        error={error}
        errorId={errorId}
        required={required}
        className={className}
      >
        <input
          {...props}
          ref={ref}
          id={fieldId}
          type={type}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={buildControlClassName(Boolean(error), inputClassName)}
          required={required}
        />
      </FieldWrapper>
    );
  },
);

TextField.displayName = "TextField";

export interface SelectFieldProps
  extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "className">,
    BaseFieldProps {}

export const SelectField = forwardRef<HTMLSelectElement, SelectFieldProps>(
  (
    {
      label,
      description,
      error,
      required,
      className,
      inputClassName,
      id,
      children,
      ...props
    },
    ref,
  ) => {
    const fallbackId = useId();
    const fieldId = id ?? fallbackId;
    const descriptionId = description ? `${fieldId}-description` : undefined;
    const errorId = error ? `${fieldId}-error` : undefined;
    const describedBy = [descriptionId, errorId].filter(Boolean).join(" ") || undefined;

    return (
      <FieldWrapper
        id={fieldId}
        label={label}
        description={description}
        descriptionId={descriptionId}
        error={error}
        errorId={errorId}
        required={required}
        className={className}
      >
        <select
          {...props}
          ref={ref}
          id={fieldId}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={buildControlClassName(Boolean(error), inputClassName)}
          required={required}
        >
          {children}
        </select>
      </FieldWrapper>
    );
  },
);

SelectField.displayName = "SelectField";

export interface TextAreaFieldProps
  extends Omit<React.TextareaHTMLAttributes<HTMLTextAreaElement>, "className">,
    BaseFieldProps {}

export const TextAreaField = forwardRef<HTMLTextAreaElement, TextAreaFieldProps>(
  (
    {
      label,
      description,
      error,
      required,
      className,
      inputClassName,
      id,
      rows = 4,
      ...props
    },
    ref,
  ) => {
    const fallbackId = useId();
    const fieldId = id ?? fallbackId;
    const descriptionId = description ? `${fieldId}-description` : undefined;
    const errorId = error ? `${fieldId}-error` : undefined;
    const describedBy = [descriptionId, errorId].filter(Boolean).join(" ") || undefined;

    return (
      <FieldWrapper
        id={fieldId}
        label={label}
        description={description}
        descriptionId={descriptionId}
        error={error}
        errorId={errorId}
        required={required}
        className={className}
      >
        <textarea
          {...props}
          ref={ref}
          id={fieldId}
          rows={rows}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={classNames(
            buildControlClassName(Boolean(error), inputClassName),
            "resize-y",
          )}
          required={required}
        />
      </FieldWrapper>
    );
  },
);

TextAreaField.displayName = "TextAreaField";

export type FormFieldComponents = {
  TextField: typeof TextField;
  SelectField: typeof SelectField;
  TextAreaField: typeof TextAreaField;
};

export const FormField: FormFieldComponents = {
  TextField,
  SelectField,
  TextAreaField,
};

export default FormField;
