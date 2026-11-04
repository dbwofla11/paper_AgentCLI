import { useRef, type KeyboardEvent } from 'react';
import { BookOpenText, ChevronRight } from 'lucide-react';
import * as m from 'motion/react-m';
import type { HarnessSkill, WorkflowPath, WorkflowStep } from '../../api/types';
import { FileLink } from '../../components/FileLink';
import { DUR_INDICATOR, DUR_ENTER, EASE_OUT, staggerDelay } from '../../motion/tokens';

/** Labels of research-workflow-map.json step kinds (same as the static guide). */
export const STEP_KINDS: Record<string, string> = {
  skill: '스킬',
  procedure: '절차',
  gate: '확인 조건',
  parallel: '병렬 역할',
  tool: '실행 도구',
  playbook: '검토 안내',
};

export function stepKind(step: WorkflowStep): string {
  return step.skill ? 'skill' : (step.kind ?? 'procedure');
}

export interface FlowSelection {
  pathId: string;
  step: number;
}

interface WorkflowGuideProps {
  paths: WorkflowPath[];
  skills: ReadonlyMap<string, HarnessSkill>;
  selection: FlowSelection;
  onSelect: (selection: FlowSelection) => void;
  onOpenSkill: (name: string) => void;
  hrefs: Record<string, string | null>;
}

function stepCaption(path: WorkflowPath, step: WorkflowStep, index: number): string {
  const position = path.layout === 'choices' ? '독립 요청' : String(index + 1);
  return `${position} · ${step.optional ? '선택' : (STEP_KINDS[stepKind(step)] ?? '절차')}`;
}

function StepDetail({ path, index, skills, onOpenSkill, hrefs }: {
  path: WorkflowPath;
  index: number;
  skills: ReadonlyMap<string, HarnessSkill>;
  onOpenSkill: (name: string) => void;
  hrefs: Record<string, string | null>;
}) {
  const step = path.steps[index];
  if (!step) return null;
  const skill = step.skill ? skills.get(step.skill) : undefined;
  const source = step.source ?? skill?.source ?? null;
  const choices = path.layout === 'choices';
  return (
    <m.div
      key={`${path.id}:${index}`}
      className="wf-detail-body"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: DUR_INDICATOR, ease: EASE_OUT }}
    >
      <p className="kicker">
        {choices ? '독립 요청 도구' : `${index + 1}단계`} · {STEP_KINDS[stepKind(step)] ?? '절차'}
        {step.optional ? ' · 선택 실행' : ''}
      </p>
      <h4 className="wf-detail-title">{step.label}</h4>
      {skill ? <p className="wf-detail-description">{skill.description}</p> : null}
      <dl className="wf-facts">
        <div>
          <dt>입력</dt>
          <dd>{step.input || '미기록'}</dd>
        </div>
        <div>
          <dt>결과</dt>
          <dd>{step.output || '미기록'}</dd>
        </div>
        <div>
          <dt>실행 조건</dt>
          <dd>{step.condition || '미기록'}</dd>
        </div>
        {choices ? null : (
          <div>
            <dt>다음 단계</dt>
            <dd>{path.steps[index + 1]?.label ?? '이 흐름의 마지막 단계'}</dd>
          </div>
        )}
        {step.members?.length ? (
          <div>
            <dt>독립 역할</dt>
            <dd>{step.members.join(' · ')}</dd>
          </div>
        ) : null}
      </dl>
      <div className="wf-detail-actions">
        {skill ? (
          <button type="button" className="btn btn-secondary btn-small" aria-haspopup="dialog" onClick={() => onOpenSkill(skill.name)}>
            <BookOpenText />
            <span>
              <code translate="no">{skill.name}</code> 설명·지침 보기
            </span>
          </button>
        ) : null}
        {source ? (
          <p className="wf-source">
            <span className="caption">근거 파일</span> <FileLink path={source} href={hrefs[source]} />
          </p>
        ) : null}
      </div>
    </m.div>
  );
}

/** 스킬 흐름: path tabs, step nodes and the selected step's detail. */
export function WorkflowGuide({ paths, skills, selection, onSelect, onOpenSkill, hrefs }: WorkflowGuideProps) {
  const tabRefs = useRef(new Map<string, HTMLButtonElement>());
  const path = paths.find((candidate) => candidate.id === selection.pathId) ?? paths[0];
  if (!path) return <p className="meta">흐름 지도를 읽지 못했습니다.</p>;
  const choices = path.layout === 'choices';

  // Tabs pattern: arrow keys, Home and End move focus and select (automatic activation).
  const moveTab = (event: KeyboardEvent<HTMLDivElement>) => {
    const current = paths.findIndex((candidate) => candidate.id === path.id);
    const target =
      event.key === 'ArrowRight' ? (current + 1) % paths.length
      : event.key === 'ArrowLeft' ? (current - 1 + paths.length) % paths.length
      : event.key === 'Home' ? 0
      : event.key === 'End' ? paths.length - 1
      : null;
    if (target === null) return;
    event.preventDefault();
    const next = paths[target];
    onSelect({ pathId: next.id, step: 0 });
    tabRefs.current.get(next.id)?.focus();
  };

  return (
    <div className="wf">
      <div className="wf-tabs" role="tablist" aria-label="작업 흐름" onKeyDown={moveTab}>
        {paths.map((candidate) => {
          const selected = candidate.id === path.id;
          return (
            <button
              key={candidate.id}
              ref={(node) => {
                if (node) tabRefs.current.set(candidate.id, node);
                else tabRefs.current.delete(candidate.id);
              }}
              type="button"
              role="tab"
              id={`wf-tab-${candidate.id}`}
              className="wf-tab"
              aria-selected={selected}
              aria-controls="wf-panel"
              tabIndex={selected ? 0 : -1}
              onClick={() => onSelect({ pathId: candidate.id, step: 0 })}
            >
              {candidate.title}
            </button>
          );
        })}
      </div>

      <div className="wf-panel" role="tabpanel" id="wf-panel" aria-labelledby={`wf-tab-${path.id}`}>
        <div className="wf-heading">
          <h3>{path.title}</h3>
          <p className="meta">{path.description}</p>
        </div>
        <ol className="wf-steps" role="list" data-layout={choices ? 'choices' : 'sequence'} aria-label="단계 선택">
          {path.steps.map((step, index) => (
            <m.li
              key={`${path.id}:${index}`}
              className="wf-step-item"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: DUR_ENTER, ease: EASE_OUT, delay: staggerDelay(index, 8) }}
            >
              {index > 0 && !choices ? <ChevronRight className="wf-arrow" /> : null}
              <button
                type="button"
                className="wf-step"
                data-kind={stepKind(step)}
                data-optional={step.optional ? 'true' : undefined}
                aria-pressed={selection.step === index}
                onClick={() => onSelect({ pathId: path.id, step: index })}
              >
                <span className="wf-step-caption">{stepCaption(path, step, index)}</span>
                <strong className="wf-step-label">{step.label}</strong>
                {step.skill ? (
                  <code className="wf-step-code" translate="no">
                    {step.skill}
                  </code>
                ) : null}
                {step.members?.length ? (
                  <span className="wf-members">
                    {step.members.map((member) => (
                      <span key={member}>{member}</span>
                    ))}
                  </span>
                ) : null}
              </button>
            </m.li>
          ))}
        </ol>
        <div className="wf-detail" aria-live="polite">
          <StepDetail path={path} index={selection.step} skills={skills} onOpenSkill={onOpenSkill} hrefs={hrefs} />
        </div>
        <p className="caption wf-note">이 그림은 실행 절차 안내이며 현재 작업의 진행 상태가 아닙니다.</p>
      </div>
    </div>
  );
}
