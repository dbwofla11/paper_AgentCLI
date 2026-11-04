import type { GraphifySync, HarnessPayload } from '../../api/types';
import { FileLink } from '../../components/FileLink';
import { formatCount } from '../../format';

type Hrefs = HarnessPayload['hrefs'];

function Presence({ ok, yes, no }: { ok: boolean; yes: string; no: string }) {
  return (
    <span className="badge" data-tone={ok ? 'success' : 'danger'}>
      {ok ? yes : no}
    </span>
  );
}

function EmptyRow({ columns, text }: { columns: number; text: string }) {
  return (
    <tr>
      <td colSpan={columns} className="meta">
        {text}
      </td>
    </tr>
  );
}

/** 라우팅: research_workflow.WORKFLOW in order. */
export function RoutingTable({ data }: { data: HarnessPayload }) {
  return (
    <>
      <p className="section-lead">
        세션 전역의 현재 단계는 따로 저장하지 않습니다. 각 요청이 선언한 단계를 라우터가 다음 스킬로 연결합니다. 라우터 정본{' '}
        <FileLink path={data.links.router} href={data.hrefs[data.links.router]} /> · 실행 원칙{' '}
        <FileLink path={data.links.harness_graph} href={data.hrefs[data.links.harness_graph]} />
      </p>
      <div className="table-scroll" tabIndex={0} role="region" aria-label="라우팅 표 (가로로 스크롤)">
        <table>
          <caption className="visually-hidden">요청 단계별 다음 스킬과 라우팅 이유</caption>
          <thead>
            <tr>
              <th scope="col">요청 단계</th>
              <th scope="col">다음 스킬</th>
              <th scope="col">라우팅 이유</th>
            </tr>
          </thead>
          <tbody>
            {data.routing.length === 0 ? <EmptyRow columns={3} text="라우터를 읽지 못했습니다." /> : null}
            {data.routing.map((row) => (
              <tr key={row.stage}>
                <th scope="row">
                  <code translate="no">{row.stage}</code>
                </th>
                <td>
                  <code translate="no">{row.next}</code>
                </td>
                <td>{row.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

/** 스킬 정본·호스트 연결: one row per .agents/skills entry. */
export function SkillLinksTable({ data }: { data: HarnessPayload }) {
  return (
    <>
      <p className="section-lead">
        Codex와 omp는 <code translate="no">.agents/skills</code> 정본을 직접 탐색합니다. Codex 호환 미러가 연결되지 않았다고
        스킬을 쓸 수 없는 것은 아닙니다.
      </p>
      <div className="table-scroll" tabIndex={0} role="region" aria-label="스킬 연결 표 (가로로 스크롤)">
        <table>
          <caption className="visually-hidden">스킬별 정본과 Claude·Codex·omp 연결 상태</caption>
          <thead>
            <tr>
              <th scope="col">스킬</th>
              <th scope="col">.agents 정본</th>
              <th scope="col">Claude 연결</th>
              <th scope="col">Codex 호환 미러</th>
              <th scope="col">omp</th>
            </tr>
          </thead>
          <tbody>
            {data.skill_links.length === 0 ? <EmptyRow columns={5} text="스킬 디렉터리를 읽지 못했습니다." /> : null}
            {data.skill_links.map((link) => (
              <tr key={link.name}>
                <th scope="row">
                  <FileLink path={link.source} href={data.hrefs[link.source]} />
                </th>
                <td>
                  <Presence ok={link.source_exists} yes="있음" no="누락" />
                </td>
                <td>
                  <Presence ok={link.claude === 'linked'} yes="연결됨" no="미연결" />
                </td>
                <td>
                  <span className="badge" data-tone={link.codex === 'linked' ? 'success' : 'neutral'}>
                    {link.codex === 'linked' ? '연결됨' : '미연결'}
                  </span>
                </td>
                <td>
                  <Presence ok={link.omp === 'direct'} yes="직접 탐색" no="누락" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

/** omp 에이전트 (with front-matter descriptions) and 페르소나. */
export function AgentsAndPersonas({ data }: { data: HarnessPayload }) {
  return (
    <div className="agents-grid">
      <div>
        <h3 className="subsection-title">
          omp 에이전트 <span className="meta num">{formatCount(data.omp_agents.length)}</span>
        </h3>
        {data.omp_agents.length === 0 ? (
          <p className="meta">omp 에이전트가 없습니다.</p>
        ) : (
          <ul className="entity-list" role="list">
            {data.omp_agents.map((agent) => (
              <li key={agent.name} className="entity">
                <p className="entity-name">
                  <code translate="no">{agent.name}</code>
                </p>
                <p className="entity-text">{agent.description ?? '설명 미기록'}</p>
                <FileLink path={agent.path} href={data.hrefs[agent.path]} />
              </li>
            ))}
          </ul>
        )}
      </div>
      <div>
        <h3 className="subsection-title">
          페르소나 <span className="meta num">{formatCount(data.personas.length)}</span>
        </h3>
        {data.personas.length === 0 ? (
          <p className="meta">필수 페르소나가 없습니다.</p>
        ) : (
          <ul className="entity-list" role="list">
            {data.personas.map((persona) => (
              <li key={persona.path} className="entity">
                <p className="entity-name">
                  <code translate="no">{persona.name}</code>
                </p>
                <FileLink path={persona.path} href={data.hrefs[persona.path]} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

/** 검증기: validator files with 있음/누락, plus the test code. */
export function ValidatorsTable({ data }: { data: HarnessPayload }) {
  return (
    <>
      <div className="table-scroll" tabIndex={0} role="region" aria-label="검증기 표 (가로로 스크롤)">
        <table>
          <caption className="visually-hidden">검증기 파일과 존재 여부</caption>
          <thead>
            <tr>
              <th scope="col">검증기</th>
              <th scope="col">파일</th>
              <th scope="col">상태</th>
            </tr>
          </thead>
          <tbody>
            {data.validators.length === 0 ? <EmptyRow columns={3} text="검증기 목록이 없습니다." /> : null}
            {data.validators.map((validator) => (
              <tr key={validator.path}>
                <th scope="row">{validator.name}</th>
                <td>
                  <FileLink path={validator.path} href={data.hrefs[validator.path]} />
                </td>
                <td>
                  <Presence ok={validator.exists} yes="있음" no="누락" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.tests_path ? (
        <p className="section-foot">
          <span className="caption">테스트 코드</span> <FileLink path={data.tests_path} href={data.hrefs[data.tests_path]} />
        </p>
      ) : null}
    </>
  );
}

/** Graphify 동기화: sync-state.json counts by status. */
export function GraphifyCard({ graphify, data }: { graphify: GraphifySync; data: HarnessPayload }) {
  const statuses = Object.entries(graphify.by_status).sort(([a], [b]) => a.localeCompare(b));
  return (
    <>
      {graphify.error ? (
        <div className="notice" data-tone="warning">
          <p className="notice-title">동기화 기록을 읽지 못했습니다.</p>
          <p className="notice-detail">{graphify.error}</p>
        </div>
      ) : !graphify.exists ? (
        <p className="section-lead">아직 동기화 기록이 없습니다. Graphify를 처음 실행하면 로컬에 기록이 생깁니다.</p>
      ) : (
        <dl className="graphify-stats">
          <div className="graphify-stat">
            <dt>기록</dt>
            <dd className="num">{formatCount(graphify.total)}</dd>
          </div>
          <div className="graphify-stat" data-pending={graphify.pending > 0 ? 'true' : undefined}>
            <dt>pending</dt>
            <dd className="num">{formatCount(graphify.pending)}</dd>
          </div>
          {statuses
            .filter(([status]) => status !== 'pending')
            .map(([status, count]) => (
              <div className="graphify-stat" key={status}>
                <dt translate="no">{status}</dt>
                <dd className="num">{formatCount(count)}</dd>
              </div>
            ))}
        </dl>
      )}
      <p className="section-foot">
        <span className="caption">로컬 생성 기록</span> <FileLink path={graphify.path} href={data.hrefs[graphify.path]} />{' '}
        <span className="caption">상태 명령</span>{' '}
        <FileLink path={data.links.graphify_sync} href={data.hrefs[data.links.graphify_sync]} />
      </p>
    </>
  );
}

/** 관리 범위. */
export function ScopeNote({ hrefs, links }: { hrefs: Hrefs; links: HarnessPayload['links'] }) {
  return (
    <>
      <p className="section-lead">이 화면은 정본 파일을 수정하지 않습니다. 검사 버튼은 서버에 고정된 두 명령만 실행합니다.</p>
      <p className="section-foot">
        <span className="caption">온보딩 도구 안내</span> <FileLink path={links.installer_doc} href={hrefs[links.installer_doc]} />{' '}
        <span className="caption">설치기</span> <FileLink path={links.installer} href={hrefs[links.installer]} />{' '}
        <span className="caption">흐름 정본</span> <FileLink path={links.workflow_map} href={hrefs[links.workflow_map]} />
      </p>
    </>
  );
}
