import { ArrowRight, X } from 'lucide-react';
import type { HarnessSkill } from '../../api/types';
import { FileLink } from '../../components/FileLink';
import { FileX } from 'lucide-react';
import { EmptyState } from '../../components/EmptyState';
import { Markdown } from '../../components/Markdown';
import { Sheet } from '../../components/Sheet';
import { formatCount } from '../../format';

const TITLE_ID = 'skill-sheet-title';

interface SkillSheetProps {
  skill: HarnessSkill | null;
  onClose: () => void;
  /** "…에서 보기": select that path step in 스킬 흐름 and scroll to it. */
  onShowUse: (pathId: string, step: number) => void;
  hrefs: Record<string, string | null>;
}

/** Skill detail sheet: where the skill is used, its SKILL.md path, and the rendered instructions. */
export function SkillSheet({ skill, onClose, onShowUse, hrefs }: SkillSheetProps) {
  return (
    <Sheet open={skill !== null} onClose={onClose} labelledBy={TITLE_ID} contentKey={skill?.name}>
      {skill ? (
        <>
          <header className="sheet-head">
            <div className="sheet-head-copy">
              <p className="eyebrow" translate="no">
                {skill.name}
              </p>
              <h2 id={TITLE_ID}>{skill.title}</h2>
              <p className="meta">{skill.description}</p>
            </div>
            <button type="button" className="icon-btn" aria-label="닫기" onClick={onClose}>
              <X />
            </button>
          </header>
          <div className="sheet-scroll">
            <section className="sheet-section" aria-labelledby="skill-sheet-uses">
              <h3 id="skill-sheet-uses">
                사용 위치 <span className="meta num">{formatCount(skill.uses.length)}곳</span>
              </h3>
              {skill.uses.length === 0 ? (
                <p className="meta">흐름 지도에 없는 독립 스킬입니다. 개별 요청으로 사용하며, 실행 범위는 아래 지침을 확인하세요.</p>
              ) : (
                <ul className="skill-uses" role="list">
                  {skill.uses.map((use) => (
                    <li key={`${use.path_id}:${use.order}`} className="skill-use">
                      <div className="skill-use-head">
                        <p>
                          <strong>{use.path_title}</strong> <span className="meta">· {use.order}단계 {use.label}</span>
                        </p>
                        <button
                          type="button"
                          className="btn btn-text btn-small"
                          onClick={() => onShowUse(use.path_id, use.order - 1)}
                        >
                          {use.path_title}에서 보기
                          <ArrowRight />
                        </button>
                      </div>
                      <dl className="wf-facts">
                        <div>
                          <dt>입력</dt>
                          <dd>{use.input || '미기록'}</dd>
                        </div>
                        <div>
                          <dt>결과</dt>
                          <dd>{use.output || '미기록'}</dd>
                        </div>
                        <div>
                          <dt>조건</dt>
                          <dd>{use.condition || '미기록'}</dd>
                        </div>
                      </dl>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <section className="sheet-section" aria-labelledby="skill-sheet-instructions">
              <div className="sheet-section-head">
                <h3 id="skill-sheet-instructions">전체 지침</h3>
                <FileLink path={skill.source} href={hrefs[skill.source]} />
              </div>
              {skill.instructions === null ? (
                <EmptyState icon={FileX} title="지침을 표시하지 않습니다">
                  <p>정적 파일 정책 밖 경로라 내용을 표시하지 않습니다.</p>
                </EmptyState>
              ) : (
                <Markdown markdown={skill.instructions} className="skill-md" />
              )}
            </section>
          </div>
        </>
      ) : null}
    </Sheet>
  );
}
