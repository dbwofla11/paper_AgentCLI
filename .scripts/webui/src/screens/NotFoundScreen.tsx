import type { Ref } from 'react';
import { SearchX } from 'lucide-react';
import { EmptyState } from '../components/EmptyState';
import { ScreenHeader } from '../components/ScreenHeader';
import { HARNESS_HREF, IDEAS_HREF, JOBS_HREF, PAPERS_HREF, STATUS_HREF } from '../hooks/useHashRoute';

export function NotFoundScreen({ headingRef, path }: { headingRef: Ref<HTMLHeadingElement>; path: string }) {
  return (
    <div className="screen">
      <ScreenHeader
        eyebrow={`#${path}`}
        title="화면을 찾을 수 없습니다"
        description="주소가 이 WebUI의 화면과 맞지 않습니다."
        headingRef={headingRef}
      />
      <EmptyState
        icon={SearchX}
        title="없는 화면입니다"
        action={
          <a className="btn btn-primary" href={PAPERS_HREF}>
            논문 라이브러리로 이동
          </a>
        }
      >
        <p>
          <code translate="no">#{path}</code> 화면은 없습니다. <a href={IDEAS_HREF}>사고실험</a>,{' '}
          <a href={HARNESS_HREF}>하네스</a>, <a href={STATUS_HREF}>상태</a> 또는 <a href={JOBS_HREF}>작업</a> 화면으로
          이동할 수도 있습니다.
        </p>
      </EmptyState>
    </div>
  );
}
