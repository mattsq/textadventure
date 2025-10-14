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

export interface AutocompleteFieldProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "className" | "onChange" | "value">,
    BaseFieldProps {
    readonly options: readonly string[];
    readonly value: string;
    readonly onValueChange: (value: string) => void;
    readonly emptyMessage?: React.ReactNode;
    readonly onChange?: React.ChangeEventHandler<HTMLInputElement>;
  }

export const AutocompleteField = forwardRef<HTMLInputElement, AutocompleteFieldProps>(
  (
    {
      label,
      description,
      error,
      required,
      className,
      inputClassName,
      id,
      options,
      value,
      onValueChange,
      emptyMessage = "No matching options found.",
      disabled = false,
      onFocus,
      onBlur,
      onKeyDown,
      onChange,
      autoComplete = "off",
      ...props
    },
    ref,
  ) => {
    const fallbackId = useId();
    const fieldId = id ?? fallbackId;
    const descriptionId = description ? `${fieldId}-description` : undefined;
    const errorId = error ? `${fieldId}-error` : undefined;
    const describedBy = [descriptionId, errorId].filter(Boolean).join(" ") || undefined;
    const listboxId = `${fieldId}-listbox`;

    const [isOpen, setIsOpen] = React.useState(false);
    const [highlightedIndex, setHighlightedIndex] = React.useState<number | null>(null);
    const inputRef = React.useRef<HTMLInputElement>(null);

    React.useImperativeHandle(ref, () => inputRef.current!, []);

    const filteredOptions = React.useMemo(() => {
      const query = value.trim().toLowerCase();
      if (!query) {
        return options;
      }
      return options.filter((option) => option.toLowerCase().includes(query));
    }, [options, value]);

    React.useEffect(() => {
      if (!isOpen) {
        setHighlightedIndex(null);
        return;
      }
      if (filteredOptions.length === 0) {
        setHighlightedIndex(null);
        return;
      }
      setHighlightedIndex((previous) => {
        if (previous === null) {
          return null;
        }
        if (previous >= filteredOptions.length) {
          return filteredOptions.length - 1;
        }
        return previous;
      });
    }, [filteredOptions, isOpen]);

    const closeListbox = React.useCallback(() => {
      setIsOpen(false);
      setHighlightedIndex(null);
    }, []);

    const commitValue = React.useCallback(
      (nextValue: string) => {
        onValueChange(nextValue);
        window.requestAnimationFrame(() => {
          inputRef.current?.focus();
        });
        closeListbox();
      },
      [closeListbox, onValueChange],
    );

    const handleFocus: React.FocusEventHandler<HTMLInputElement> = (event) => {
      onFocus?.(event);
      if (!disabled) {
        setIsOpen(true);
      }
    };

    const handleBlur: React.FocusEventHandler<HTMLInputElement> = (event) => {
      onBlur?.(event);
      window.setTimeout(() => {
        closeListbox();
      }, 100);
    };

    const handleKeyDown: React.KeyboardEventHandler<HTMLInputElement> = (event) => {
      if (disabled) {
        onKeyDown?.(event);
        return;
      }

      if (!isOpen && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
        setIsOpen(true);
      }

      if (event.key === "ArrowDown") {
        if (filteredOptions.length === 0) {
          return;
        }
        event.preventDefault();
        setHighlightedIndex((previous) => {
          if (previous === null) {
            return 0;
          }
          return Math.min(previous + 1, filteredOptions.length - 1);
        });
        return;
      }

      if (event.key === "ArrowUp") {
        if (filteredOptions.length === 0) {
          return;
        }
        event.preventDefault();
        setHighlightedIndex((previous) => {
          if (previous === null) {
            return filteredOptions.length - 1;
          }
          return Math.max(previous - 1, 0);
        });
        return;
      }

      if (event.key === "Enter" && highlightedIndex !== null && filteredOptions[highlightedIndex]) {
        event.preventDefault();
        commitValue(filteredOptions[highlightedIndex]);
        return;
      }

      if (event.key === "Escape") {
        closeListbox();
        return;
      }

      onKeyDown?.(event);
    };

    const handleChange: React.ChangeEventHandler<HTMLInputElement> = (event) => {
      onChange?.(event);
      onValueChange(event.target.value);
      if (!disabled) {
        setIsOpen(true);
      }
    };

    const handleOptionMouseDown: React.MouseEventHandler<HTMLLIElement> = (event) => {
      // Prevent input blur before onClick fires.
      event.preventDefault();
    };

    const handleOptionClick = (option: string) => {
      commitValue(option);
    };

    const activeDescendant =
      highlightedIndex !== null && filteredOptions[highlightedIndex]
        ? `${listboxId}-${highlightedIndex}`
        : undefined;

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
        <div className="relative">
          <input
            {...props}
            ref={inputRef}
            id={fieldId}
            role="combobox"
            aria-expanded={isOpen}
            aria-controls={listboxId}
            aria-autocomplete="list"
            aria-activedescendant={activeDescendant}
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy}
            value={value}
            onChange={handleChange}
            onFocus={handleFocus}
            onBlur={handleBlur}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            autoComplete={autoComplete}
            className={buildControlClassName(Boolean(error), inputClassName)}
            required={required}
          />
          {isOpen ? (
            <ul
              id={listboxId}
              role="listbox"
              className="absolute left-0 right-0 z-10 mt-1 max-h-60 overflow-y-auto rounded-lg border border-slate-700/70 bg-slate-900/95 shadow-lg shadow-black/40"
            >
              {filteredOptions.length === 0 ? (
                <li
                  className="px-3 py-2 text-xs text-slate-400"
                  role="presentation"
                >
                  {emptyMessage}
                </li>
              ) : (
                filteredOptions.map((option, index) => {
                  const optionId = `${listboxId}-${index}`;
                  const isActive = index === highlightedIndex;
                  return (
                    <li
                      key={option}
                      id={optionId}
                      role="option"
                      aria-selected={isActive}
                      className={classNames(
                        "cursor-pointer px-3 py-2 text-sm text-slate-100 transition",
                        isActive
                          ? "bg-indigo-500/80 text-white"
                          : "hover:bg-slate-800/70",
                      )}
                      onMouseDown={handleOptionMouseDown}
                      onClick={() => handleOptionClick(option)}
                    >
                      {option}
                    </li>
                  );
                })
              )}
            </ul>
          ) : null}
        </div>
      </FieldWrapper>
    );
  },
);

AutocompleteField.displayName = "AutocompleteField";

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
  AutocompleteField: typeof AutocompleteField;
  SelectField: typeof SelectField;
  TextAreaField: typeof TextAreaField;
};

export const FormField: FormFieldComponents = {
  TextField,
  AutocompleteField,
  SelectField,
  TextAreaField,
};

export default FormField;
