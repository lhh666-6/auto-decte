export interface FilterOption {
  key: string;
  label: string;
  options?: Array<{ value: string; label: string }>;
}

export interface AppliedFilter {
  key: string;
  value: string;
}

export interface FilterToolbarProps {
  /** Preferred: filter definitions */
  filters?: FilterOption[];
  /** Alias for filters (FinanceLedgerPage compat) */
  options?: FilterOption[];
  /** Currently applied filters */
  applied?: AppliedFilter[];
  /** Alias for applied (FinanceLedgerPage compat) */
  filtersValue?: AppliedFilter[];
  /** Called when any filter changes */
  onChange?: (applied: AppliedFilter[]) => void;
  /** FinanceLedgerPage compat: called when a filter is applied */
  onApply?: (filter: AppliedFilter) => void;
  /** FinanceLedgerPage compat: called when a filter is removed */
  onRemove?: (key: string) => void;
}

export function FilterToolbar(props: FilterToolbarProps) {
  const filterDefs = props.filters ?? props.options ?? [];
  const currentApplied = props.applied ?? props.filtersValue ?? [];

  function updateFilter(key: string, value: string) {
    if (props.onChange) {
      const next = currentApplied.filter((f) => f.key !== key);
      if (value) {
        next.push({ key, value });
      }
      props.onChange(next);
    }
  }

  function handleSelectChange(key: string, value: string) {
    if (props.onChange) {
      updateFilter(key, value);
    } else if (props.onApply && value) {
      props.onApply({ key, value });
    } else if (props.onRemove && !value) {
      props.onRemove(key);
    }
  }

  function removeChip(key: string) {
    if (props.onChange) {
      const next = currentApplied.filter((f) => f.key !== key);
      props.onChange(next);
    } else if (props.onRemove) {
      props.onRemove(key);
    }
  }

  function clearAll() {
    if (props.onChange) {
      props.onChange([]);
    }
  }

  function chipLabel(filter: AppliedFilter): string {
    const def = filterDefs.find((f) => f.key === filter.key);
    const optLabel = def?.options?.find((o) => o.value === filter.value)?.label;
    const prefix = def?.label ?? filter.key;
    return `${prefix}：${optLabel ?? filter.value}`;
  }

  return (
    <div className="finance-filter-toolbar">
      <div className="finance-filter-form">
        {filterDefs.map((filter) => {
          const current = currentApplied.find((f) => f.key === filter.key)?.value ?? "";
          return (
            <label key={filter.key}>
              {filter.label}
              <select
                className="finance-filter-select"
                value={current}
                onChange={(e) => handleSelectChange(filter.key, e.target.value)}
              >
                <option value="">全部</option>
                {(filter.options ?? []).map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </label>
          );
        })}
      </div>

      {currentApplied.length > 0 && (
        <div className="finance-filter-chips">
          {currentApplied.map((f) => (
            <span key={f.key} className="finance-filter-chip">
              {chipLabel(f)}
              <button
                type="button"
                className="finance-filter-chip-remove"
                onClick={() => removeChip(f.key)}
                aria-label={`移除筛选 ${chipLabel(f)}`}
              >
                ×
              </button>
            </span>
          ))}
          <button
            type="button"
            className="finance-filter-clear-all"
            onClick={clearAll}
          >
            清除全部
          </button>
        </div>
      )}
    </div>
  );
}
