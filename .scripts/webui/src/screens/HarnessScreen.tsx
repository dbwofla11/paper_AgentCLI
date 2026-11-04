import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode, type Ref } from 'react';
import {
  Bot,
  GitBranch,
  Info,
  Library,
  ListChecks,
  Network,
  RefreshCw,
  Route,
  ShieldCheck,
  Workflow,
  type LucideIcon,
} from 'lucide-react';
import * as m from 'motion/react-m';
import { useReducedMotion } from 'motion/react';
import { fetchHarness, toApiError, type ApiError } from '../api/client';
import type { HarnessPayload } from '../api/types';
import { ErrorNotice } from '../components/ErrorNotice';
import { ScreenHeader } from '../components/ScreenHeader';
import { Skeleton } from '../components/Skeleton';
import { DUR_INDICATOR, EASE_OUT, ENTER_FROM, ENTER_TO, enterTransition } from '../motion/tokens';
import { HarnessChecks } from './harness/HarnessChecks';
import {
  AgentsAndPersonas,
  GraphifyCard,
  RoutingTable,
  ScopeNote,
  SkillLinksTable,
  ValidatorsTable,
} from './harness/HarnessTables';
import { SkillCatalog } from './harness/SkillCatalog';
import { SkillSheet } from './harness/SkillSheet';
import { WorkflowGuide, type FlowSelection } from './harness/WorkflowGuide';
import '../styles/harness.css';

interface SectionDef {
  id: string;
  label: string;
  icon: LucideIcon;
  description?: string;
}

const SECTIONS: readonly SectionDef[] = [
  { id: 'harness-flow', label: '스킬 흐름', icon: Workflow, description: '작업 흐름을 고르고 단계를 누르면 입력·결과·실행 조건과 다음 단계가 표시됩니다.' },
  { id: 'harness-skills', label: '스킬 카탈로그', icon: Library, description: '카드를 누르면 사용 위치와 전체 SKILL.md 지침이 열립니다.' },
  { id: 'harness-checks', label: '검사', icon: ShieldCheck, description: '서버가 저장소 루트에서 고정 명령을 실행하고 출력을 실시간으로 보여 줍니다.' },
  { id: 'harness-routing', label: '라우팅', icon: Route },
  { id: 'harness-links', label: '스킬 정본·호스트 연결', icon: GitBranch },
  { id: 'harness-agents', label: 'omp 에이전트·페르소나', icon: Bot },
  { id: 'harness-validators', label: '검증기', icon: ListChecks },
  { id: 'harness-graphify', label: 'Graphify 동기화', icon: Network },
  { id: 'harness-scope', label: '관리 범위', icon: Info },
];

const ERROR_SECTIONS: Record<string, string> = {
  guide: '스킬 흐름·카탈로그',
  routing: '라우팅',
  skill_links: '스킬 정본·호스트 연결',
  omp_agents: 'omp 에이전트',
  personas: '페르소나',
  validators: '검증기',
  graphify: 'Graphify 동기화',
};

interface LoadState {
  data: HarnessPayload | null;
  error: ApiError | null;
  loading: boolean;
}

function Section({ def, index, children }: { def: SectionDef; index: number; children: ReactNode }) {
  const Icon = def.icon;
  return (
    <m.section
      id={def.id}
      className="harness-section card"
      aria-labelledby={`${def.id}-title`}
      initial={ENTER_FROM}
      animate={ENTER_TO}
      transition={enterTransition(index, 8)}
    >
      <div className="harness-section-head">
        <span className="harness-section-icon">
          <Icon />
        </span>
        <div>
          <h2 id={`${def.id}-title`} tabIndex={-1}>
            {def.label}
          </h2>
          {def.description ? <p className="meta">{def.description}</p> : null}
        </div>
      </div>
      {children}
    </m.section>
  );
}

/** Sticky section index (≥ 1024px). Buttons, not links: the URL hash belongs to the router. */
function SectionNav({ active, onJump }: { active: string; onJump: (id: string) => void }) {
  return (
    <nav className="harness-nav" aria-label="하네스 구역">
      <ul role="list">
        {SECTIONS.map((section) => (
          <li key={section.id}>
            <button
              type="button"
              className="harness-nav-item"
              aria-current={section.id === active ? 'true' : undefined}
              onClick={() => onJump(section.id)}
            >
              {section.id === active ? (
                <m.span
                  className="harness-nav-indicator"
                  layoutId="harness-nav-indicator"
                  transition={{ duration: DUR_INDICATOR, ease: EASE_OUT }}
                  aria-hidden="true"
                />
              ) : null}
              {section.label}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}

/** Topmost section in the upper part of the viewport. */
function useActiveSection(ready: boolean): [string, (id: string) => void] {
  const [active, setActive] = useState(SECTIONS[0].id);
  useEffect(() => {
    if (!ready) return;
    const visible = new Set<string>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) visible.add(entry.target.id);
          else visible.delete(entry.target.id);
        }
        const first = SECTIONS.find((section) => visible.has(section.id));
        if (first) setActive(first.id);
      },
      { rootMargin: '-80px 0px -55% 0px' },
    );
    for (const section of SECTIONS) {
      const element = document.getElementById(section.id);
      if (element) observer.observe(element);
    }
    return () => observer.disconnect();
  }, [ready]);
  return [active, setActive];
}

/** `#/harness`: skill flow, catalog, checks, and the harness wiring tables. */
export default function HarnessScreen({ headingRef, reloadToken }: { headingRef: Ref<HTMLHeadingElement>; reloadToken: number }) {
  const [state, setState] = useState<LoadState>({ data: null, error: null, loading: true });
  const [selection, setSelection] = useState<FlowSelection | null>(null);
  const [openSkill, setOpenSkill] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const reduceMotion = useReducedMotion();

  const load = useCallback(() => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setState((previous) => ({ ...previous, loading: true }));
    fetchHarness(controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) setState({ data, error: null, loading: false });
      },
      (error: unknown) => {
        if (!controller.signal.aborted) setState((previous) => ({ ...previous, error: toApiError(error), loading: false }));
      },
    );
  }, []);

  useEffect(() => {
    load();
    return () => controllerRef.current?.abort();
  }, [load, reloadToken]);

  const { data, error, loading } = state;
  const skills = useMemo(() => new Map(data?.guide.skills.map((skill) => [skill.name, skill])), [data]);
  const [activeSection, setActiveSection] = useActiveSection(data !== null);
  const flowSelection = selection ?? { pathId: data?.guide.paths[0]?.id ?? '', step: 0 };

  const jumpTo = useCallback(
    (id: string) => {
      const section = document.getElementById(id);
      if (!section) return;
      section.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
      section.querySelector<HTMLElement>('h2')?.focus({ preventScroll: true });
      setActiveSection(id);
    },
    [reduceMotion, setActiveSection],
  );

  const showUse = (pathId: string, step: number) => {
    setOpenSkill(null);
    setSelection({ pathId, step });
    // Wait for the sheet to close (focus returns to its opener) before moving to the flow.
    window.requestAnimationFrame(() => jumpTo('harness-flow'));
  };

  const sectionBody = (id: string, payload: HarnessPayload): ReactNode => {
    switch (id) {
      case 'harness-flow':
        return (
          <WorkflowGuide
            paths={payload.guide.paths}
            skills={skills}
            selection={flowSelection}
            onSelect={setSelection}
            onOpenSkill={setOpenSkill}
            hrefs={payload.hrefs}
          />
        );
      case 'harness-skills':
        return <SkillCatalog skills={payload.guide.skills} onOpen={setOpenSkill} />;
      case 'harness-checks':
        return <HarnessChecks checks={payload.checks} reloadToken={reloadToken} />;
      case 'harness-routing':
        return <RoutingTable data={payload} />;
      case 'harness-links':
        return <SkillLinksTable data={payload} />;
      case 'harness-agents':
        return <AgentsAndPersonas data={payload} />;
      case 'harness-validators':
        return <ValidatorsTable data={payload} />;
      case 'harness-graphify':
        return <GraphifyCard graphify={payload.graphify} data={payload} />;
      default:
        return <ScopeNote hrefs={payload.hrefs} links={payload.links} />;
    }
  };

  return (
    <div className="screen harness">
      <ScreenHeader
        eyebrow=".agents/skills · .omp/agents"
        title="하네스"
        description="스킬을 언제 어떤 순서로 쓰는지 살펴보고, 정본·호스트 연결 상태를 확인하고, 하네스 구조 검사와 테스트를 실행합니다."
        headingRef={headingRef}
      >
        <button type="button" className="btn btn-secondary" onClick={load} disabled={loading} aria-busy={loading}>
          <RefreshCw />
          {loading ? '불러오는 중…' : '새로 고침'}
        </button>
      </ScreenHeader>

      {error && error.code !== 'offline' ? (
        <ErrorNotice
          error={error}
          title={data ? '하네스 정보를 다시 불러오지 못했습니다. 아래는 이전 결과입니다.' : '하네스 정보를 불러오지 못했습니다.'}
          onRetry={load}
        />
      ) : null}

      {data && data.errors.length > 0 ? (
        <div className="notice" data-tone="warning" role="status">
          <p className="notice-title">일부 구역을 읽지 못했습니다.</p>
          <ul>
            {data.errors.map((item) => (
              <li key={`${item.section}:${item.error}`}>
                {ERROR_SECTIONS[item.section] ?? item.section}: {item.error}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {data ? (
        <div className="harness-layout">
          <SectionNav active={activeSection} onJump={jumpTo} />
          <div className="harness-content">
            {SECTIONS.map((def, index) => (
              <Section key={def.id} def={def} index={index}>
                {sectionBody(def.id, data)}
              </Section>
            ))}
          </div>
        </div>
      ) : loading ? (
        <div className="harness-layout" role="status">
          <span className="visually-hidden">하네스 정보를 불러오는 중…</span>
          <div className="harness-nav" aria-hidden="true">
            <Skeleton height="18rem" />
          </div>
          <div className="harness-content" aria-hidden="true">
            <Skeleton height="22rem" radius="var(--radius-md)" />
            <Skeleton height="16rem" radius="var(--radius-md)" />
          </div>
        </div>
      ) : error?.code === 'offline' ? (
        <p className="empty">서버를 실행하고 ‘다시 연결’을 누르면 하네스 정보를 다시 불러옵니다.</p>
      ) : null}

      {data ? (
        <SkillSheet
          skill={openSkill ? (skills.get(openSkill) ?? null) : null}
          onClose={() => setOpenSkill(null)}
          onShowUse={showUse}
          hrefs={data.hrefs}
        />
      ) : null}
    </div>
  );
}
