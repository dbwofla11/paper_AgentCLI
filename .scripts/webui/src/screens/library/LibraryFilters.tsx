import { useId } from 'react';
import { Search } from 'lucide-react';
import { FilterSelect } from '../../components/FilterSelect';
import { formatCount } from '../../format';
import { isFiltered, type FilterOption, type LibraryFilter } from './stats';

interface LibraryFiltersProps {
  filter: LibraryFilter;
  onChange: (filter: LibraryFilter) => void;
  options: { categories: FilterOption[]; statuses: FilterOption[]; years: FilterOption[] };
  shown: number;
  total: number;
  onReset: () => void;
}

/** Search, three selects and the PDF switch, each with a visible label, plus the "N / M편" line. */
export function LibraryFilters({ filter, onChange, options, shown, total, onReset }: LibraryFiltersProps) {
  const searchId = useId();
  const set = (patch: Partial<LibraryFilter>) => onChange({ ...filter, ...patch });
  return (
    <div className="library-filters" role="search" aria-label="논문 찾기">
      <div className="field library-search">
        <label htmlFor={searchId}>검색</label>
        <span className="search-input">
          <Search />
          <input
            id={searchId}
            type="search"
            name="q"
            placeholder="제목, 저자, 주제, 초록, 학회로 찾기…"
            autoComplete="off"
            spellCheck={false}
            value={filter.query}
            onChange={(event) => set({ query: event.currentTarget.value })}
          />
        </span>
      </div>
      <FilterSelect label="분야" value={filter.category} options={options.categories} onChange={(category) => set({ category })} />
      <FilterSelect label="읽기 상태" value={filter.status} options={options.statuses} onChange={(status) => set({ status })} />
      <FilterSelect label="연도" value={filter.year} options={options.years} onChange={(year) => set({ year })} />
      <div className="library-filters-foot">
        <label className="switch">
          <input
            type="checkbox"
            role="switch"
            checked={filter.pdfOnly}
            onChange={(event) => set({ pdfOnly: event.currentTarget.checked })}
          />
          <span className="switch-track" aria-hidden="true" />
          PDF 있는 논문만
        </label>
        <div className="library-count-row">
          <p className="library-count" role="status">
            <span className="num">{formatCount(shown)}</span> / <span className="num">{formatCount(total)}</span>편
          </p>
          {isFiltered(filter) ? (
            <button type="button" className="btn btn-text btn-small" onClick={onReset}>
              필터 초기화
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
