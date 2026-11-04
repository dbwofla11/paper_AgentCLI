import { useId } from 'react';
import { Search } from 'lucide-react';
import { FilterSelect } from '../../components/FilterSelect';
import { formatCount } from '../../format';
import { IDEA_FILTER_FIELDS, isIdeaFiltered, type IdeaFilter, type IdeaFilterKey, type IdeaSort } from './ideas';

interface IdeaFiltersProps {
  filter: IdeaFilter;
  onChange: (filter: IdeaFilter) => void;
  options: Record<IdeaFilterKey, { value: string; label: string }[]>;
  shown: number;
  total: number;
  onReset: () => void;
}

/** Search, the six state selects of the static page and the sort order, each with a visible label. */
export function IdeaFilters({ filter, onChange, options, shown, total, onReset }: IdeaFiltersProps) {
  const searchId = useId();
  const sortId = useId();
  const set = (patch: Partial<IdeaFilter>) => onChange({ ...filter, ...patch });
  return (
    <div className="ideas-filters" role="search" aria-label="사고실험 찾기">
      <div className="field ideas-search">
        <label htmlFor={searchId}>검색</label>
        <span className="search-input">
          <Search />
          <input
            id={searchId}
            type="search"
            name="q"
            placeholder="제목이나 가설로 찾기…"
            autoComplete="off"
            spellCheck={false}
            value={filter.query}
            onChange={(event) => set({ query: event.currentTarget.value })}
          />
        </span>
      </div>
      <div className="field ideas-sort">
        <label htmlFor={sortId}>정렬</label>
        <select id={sortId} value={filter.sort} onChange={(event) => set({ sort: event.currentTarget.value as IdeaSort })}>
          <option value="date">갱신일 최신순</option>
          <option value="title">제목순</option>
        </select>
      </div>
      {IDEA_FILTER_FIELDS.map(({ key, label }) => (
        <FilterSelect key={key} label={label} value={filter[key]} options={options[key]} onChange={(value) => set({ [key]: value })} />
      ))}
      <div className="ideas-filters-foot">
        <p className="library-count" role="status">
          <span className="num">{formatCount(shown)}</span> / <span className="num">{formatCount(total)}</span>개
        </p>
        {isIdeaFiltered(filter) ? (
          <button type="button" className="btn btn-text btn-small" onClick={onReset}>
            필터 초기화
          </button>
        ) : null}
      </div>
    </div>
  );
}
