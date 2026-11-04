import { useDeferredValue, useId, useState } from 'react';
import { Search, SearchX } from 'lucide-react';
import type { HarnessSkill } from '../../api/types';
import { EmptyState } from '../../components/EmptyState';
import { formatCount } from '../../format';

function searchText(skill: HarnessSkill): string {
  return [
    skill.name,
    skill.title,
    skill.description,
    ...skill.uses.flatMap((use) => [use.label, use.input, use.output, use.condition, use.path_title]),
  ]
    .join('\n')
    .toLocaleLowerCase('ko-KR');
}

/** 스킬 카탈로그: search, "N / M개 스킬", and cards that open the skill sheet. */
export function SkillCatalog({ skills, onOpen }: { skills: HarnessSkill[]; onOpen: (name: string) => void }) {
  const [query, setQuery] = useState('');
  const deferred = useDeferredValue(query);
  const searchId = useId();
  const needle = deferred.trim().toLocaleLowerCase('ko-KR');
  const matches = needle ? skills.filter((skill) => searchText(skill).includes(needle)) : skills;

  return (
    <div className="skill-catalog">
      <div className="skill-catalog-tools">
        <div className="field">
          <label htmlFor={searchId}>스킬 검색</label>
          <span className="search-input">
            <Search />
            <input
              id={searchId}
              type="search"
              name="skill-q"
              placeholder="예: 논문 정독, 반증, keep, graphify…"
              autoComplete="off"
              spellCheck={false}
              value={query}
              onChange={(event) => setQuery(event.currentTarget.value)}
            />
          </span>
        </div>
        <p className="skill-count" role="status">
          <span className="num">{formatCount(matches.length)}</span> / <span className="num">{formatCount(skills.length)}</span>
          개 스킬
        </p>
      </div>
      {matches.length === 0 ? (
        <EmptyState
          icon={SearchX}
          title="검색 조건에 맞는 스킬이 없습니다"
          action={
            <button type="button" className="btn btn-secondary" onClick={() => setQuery('')}>
              검색 지우기
            </button>
          }
        />
      ) : (
        <ul className="skill-grid" role="list">
          {matches.map((skill) => {
            const use = skill.uses[0];
            return (
              <li key={skill.name}>
                <button type="button" className="skill-card" aria-haspopup="dialog" onClick={() => onOpen(skill.name)}>
                  <code className="skill-card-name" translate="no">
                    {skill.name}
                  </code>
                  <strong className="skill-card-title">{use?.label ?? skill.title}</strong>
                  <span className="skill-card-text">{use ? `${use.input} → ${use.output}` : skill.description}</span>
                  <span className="skill-card-foot caption">
                    {skill.uses.length > 0 ? `흐름 ${formatCount(skill.uses.length)}곳에서 사용` : '개별 요청으로 사용'}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
