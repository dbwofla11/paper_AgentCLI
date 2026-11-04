import { CircleAlert } from 'lucide-react';
import type { ApiError } from '../api/client';

/** Korean guidance for error codes from the server guards and the client transport. */
const CODE_HINTS: Record<string, string> = {
  offline: '로컬 서버가 응답하지 않습니다. 서버를 실행한 뒤 다시 시도하세요.',
  timeout: '서버 응답이 늦습니다. 잠시 후 다시 시도하세요.',
  bad_host: '허용된 주소가 아닙니다. 서버가 터미널에 출력한 http://127.0.0.1:<포트>/100-views/webui/ 주소로 여세요.',
  bad_origin: '같은 출처에서 보낸 요청만 허용됩니다. 화면을 새로 고친 뒤 다시 시도하세요.',
  bad_csrf: '세션 토큰이 맞지 않습니다. 화면을 새로 고친 뒤 다시 시도하세요.',
  bad_response: '서버 응답 형식이 올바르지 않습니다. 서버와 화면이 같은 버전인지 확인하세요.',
};

interface ErrorNoticeProps {
  error: ApiError;
  title: string;
  onRetry?: () => void;
  retryLabel?: string;
}

export function ErrorNotice({ error, title, onRetry, retryLabel = '다시 시도' }: ErrorNoticeProps) {
  const hint = CODE_HINTS[error.code];
  return (
    <div className="notice" data-tone="danger" role="alert">
      <p className="notice-title">
        <CircleAlert />
        {title}
      </p>
      {hint ? <p>{hint}</p> : null}
      <p className="notice-detail">
        <code translate="no">{error.code}</code> {error.message}
      </p>
      {onRetry ? (
        <div className="notice-actions">
          <button type="button" className="btn btn-secondary btn-small" onClick={onRetry}>
            {retryLabel}
          </button>
        </div>
      ) : null}
    </div>
  );
}
