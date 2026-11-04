import { useId, type ReactNode } from 'react';
import { ArrowRight, TriangleAlert } from 'lucide-react';
import * as m from 'motion/react-m';
import type { Idea } from '../../api/types';
import { FileLink } from '../../components/FileLink';
import { formatCount } from '../../format';
import { paperHref } from '../../hooks/useHashRoute';
import { DUR_ENTER, DUR_FILTER, EASE_OUT, staggerDelay } from '../../motion/tokens';
import { UNRECORDED, librarySlug, reviewParts, stateTone } from './ideas';

/** First-mount stagger stops growing after this many cards. */
const STAGGER_CAP = 11;
/** Longer path lists collapse behind a disclosure. */
const INLINE_PATHS = 3;

type Hrefs = Record<string, string | null>;

function PathList({ paths, hrefs, noun }: { paths: readonly string[]; hrefs: Hrefs; noun: string }) {
  const list = (
    <ul className="idea-path-list" role="list">
      {paths.map((path, index) => (
        <li key={`${index}:${path}`}>
          <FileLink path={path} href={hrefs[path]} />
        </li>
      ))}
    </ul>
  );
  if (paths.length <= INLINE_PATHS) return list;
  return (
    <details className="idea-paths-more">
      <summary>
        {noun} <span className="num">{formatCount(paths.length)}</span>개
      </summary>
      {list}
    </details>
  );
}

function LinkRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="idea-link-row">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

/** Related papers: library records open in the reader; IDs without a record are listed as text. */
function RelatedPapers({ idea, hrefs }: { idea: Idea; hrefs: Hrefs }) {
  const missing = idea.papers.length - idea.paperPaths.length;
  return (
    <>
      {idea.paperPaths.length > 0 ? (
        <ul className="idea-path-list" role="list">
          {idea.paperPaths.map((path) => {
            const slug = librarySlug(path);
            return (
              <li key={path}>
                {slug ? (
                  <a className="idea-paper-link" href={paperHref(slug)}>
                    <code translate="no">{slug}</code>
                    <ArrowRight aria-hidden="true" />
                    <span className="visually-hidden"> 리더에서 열기</span>
                  </a>
                ) : (
                  <FileLink path={path} href={hrefs[path]} />
                )}
              </li>
            );
          })}
        </ul>
      ) : null}
      {missing > 0 ? (
        <p className="caption idea-paper-ids">
          문헌 검토에 포함된 <span className="num">{formatCount(idea.papers.length)}</span>편 중{' '}
          <span className="num">{formatCount(missing)}</span>편은 라이브러리 기록이 없습니다:{' '}
          {idea.papers.map((id, index) => (
            <span key={`${index}:${id}`}>
              {index > 0 ? ', ' : null}
              <code translate="no">{id}</code>
            </span>
          ))}
        </p>
      ) : null}
    </>
  );
}

function Conflict({ idea }: { idea: Idea }) {
  const rows = [
    idea.statusConflict ? { label: '상태', note: idea.noteStatus, registry: idea.registry.overall || UNRECORDED } : null,
    idea.decisionConflict ? { label: '결정', note: idea.noteDecision, registry: idea.registry.decision || UNRECORDED } : null,
  ].filter((row) => row !== null);
  return (
    <div className="notice idea-conflict" data-tone="warning" role="note">
      <p className="notice-title">
        <TriangleAlert />
        노트와 심사 레지스트리가 서로 다릅니다
      </p>
      <dl className="idea-conflict-rows">
        {rows.map((row) => (
          <div key={row.label}>
            <dt>{row.label}</dt>
            <dd>
              노트 “{row.note}” · 레지스트리 “{row.registry}”
            </dd>
          </div>
        ))}
      </dl>
      <p className="idea-conflict-hint">
        어느 쪽도 자동으로 적용하지 않았습니다. 아이디어 노트나 <code translate="no">CRITICAL_VALIDATION_REGISTRY.md</code>를 직접
        맞추세요.
      </p>
    </div>
  );
}

interface IdeaCardProps {
  idea: Idea;
  hrefs: Hrefs;
  index: number;
  /** First render of the list: staggered rise. Later mounts (filter changes): opacity only. */
  entrance: 'stagger' | 'fade';
}

/** One thought experiment: states, hypothesis and falsification, conflicts and every linked file. */
export function IdeaCard({ idea, hrefs, index, entrance }: IdeaCardProps) {
  const titleId = useId();
  const roles = reviewParts(idea.review);
  const stagger = entrance === 'stagger';
  const singles: ReadonlyArray<[string, string]> = [
    ['아이디어 노트', idea.note],
    ['분석 brief', idea.brief],
    ['분석 JSON', idea.analysis],
    ['manifest', idea.manifest],
    ['실험 결과', idea.results],
    ['조사 TODO', idea.todo],
  ];
  const lists: ReadonlyArray<[string, readonly string[], string]> = [
    ['조사 결과', idea.todoResults, '결과 파일'],
    ['심사 의견', idea.critiques, '심사 의견'],
    ['근거', idea.evidence, '근거 파일'],
  ];
  const hasPapers = idea.papers.length > 0 || idea.paperPaths.length > 0;
  const states: ReadonlyArray<[string, string]> = [
    ['심사 상태', idea.validation],
    ['사용자 결정', idea.decision],
    ['문헌', idea.literature],
    ['실험', idea.experiment],
    ['조사 TODO', idea.todoStatus],
  ];

  return (
    <m.li
      className="idea-card card"
      aria-labelledby={titleId}
      initial={stagger ? { opacity: 0, y: 16 } : { opacity: 0 }}
      animate={{ opacity: 1, y: 0 }}
      transition={
        stagger
          ? { duration: DUR_ENTER, ease: EASE_OUT, delay: staggerDelay(index, STAGGER_CAP) }
          : { duration: DUR_FILTER, ease: EASE_OUT }
      }
    >
      <div className="idea-card-head">
        <p className="idea-card-facts caption">
          {idea.updated ? <span>갱신 {idea.updated}</span> : null}
          <span translate="no">{idea.id}</span>
        </p>
        <h3 className="idea-card-title" id={titleId}>
          {idea.title}
        </h3>
        <dl className="idea-states">
          {states.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>
                <span className="badge" data-tone={stateTone(value)}>
                  {value}
                </span>
              </dd>
            </div>
          ))}
        </dl>
      </div>

      {idea.decisionConflict || idea.statusConflict ? <Conflict idea={idea} /> : null}

      <dl className="idea-facts">
        <div>
          <dt>핵심 가설</dt>
          <dd className="idea-hypothesis" data-unrecorded={idea.hypothesis === UNRECORDED || undefined}>
            {idea.hypothesis}
          </dd>
        </div>
        <div>
          <dt>반증 조건</dt>
          <dd data-unrecorded={idea.falsification === UNRECORDED || undefined}>{idea.falsification}</dd>
        </div>
        <div>
          <dt>역할 심사</dt>
          <dd>
            {roles ? (
              <span className="idea-roles">
                {roles.map((role) => (
                  <span key={role.role} className="badge" data-tone={stateTone(role.status)}>
                    {role.label} {role.status}
                  </span>
                ))}
              </span>
            ) : (
              idea.review
            )}
          </dd>
        </div>
        {idea.topics !== UNRECORDED ? (
          <div>
            <dt>주제</dt>
            <dd>{idea.topics}</dd>
          </div>
        ) : null}
      </dl>

      <div className="idea-links">
        <h4 className="idea-links-title">연결 파일</h4>
        <dl className="idea-link-list">
          {singles.map(([label, path]) =>
            path ? (
              <LinkRow key={label} label={label}>
                <FileLink path={path} href={hrefs[path]} />
              </LinkRow>
            ) : null,
          )}
          {idea.todoTasks.length > 0 ? (
            <LinkRow label="조사 작업">
              <span className="idea-task-ids">
                {idea.todoTasks.map((task, index) => (
                  <code key={`${index}:${task}`} translate="no">
                    {task}
                  </code>
                ))}
              </span>
            </LinkRow>
          ) : null}
          {lists.map(([label, paths, noun]) =>
            paths.length > 0 ? (
              <LinkRow key={label} label={label}>
                <PathList paths={paths} hrefs={hrefs} noun={noun} />
              </LinkRow>
            ) : null,
          )}
          {hasPapers ? (
            <LinkRow label="관련 논문">
              <RelatedPapers idea={idea} hrefs={hrefs} />
            </LinkRow>
          ) : null}
          {idea.artifacts.length > 0 ? (
            <LinkRow label="산출물">
              <PathList paths={idea.artifacts} hrefs={hrefs} noun="산출물" />
            </LinkRow>
          ) : null}
        </dl>
      </div>
    </m.li>
  );
}
