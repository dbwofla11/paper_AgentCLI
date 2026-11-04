import { useState } from 'react';
import { Plug } from 'lucide-react';
import { CopyButton } from './CopyButton';

const SERVE_COMMAND = 'python3 .scripts/bin/research_webui.py serve';

type RetryState = 'idle' | 'retrying' | 'failed';

/** Shown above every screen while the local WebUI server is unreachable. */
export function ServerDown({ onRetry }: { onRetry: () => Promise<boolean> }) {
  const [retry, setRetry] = useState<RetryState>('idle');

  const reconnect = async () => {
    setRetry('retrying');
    setRetry((await onRetry()) ? 'idle' : 'failed');
  };

  return (
    <section className="server-down" aria-labelledby="server-down-title">
      <span className="server-down-icon">
        <Plug />
      </span>
      <div className="server-down-body">
        <div role="alert">
          <h2 id="server-down-title">로컬 서버에 연결할 수 없습니다</h2>
          <p>
            WebUI 서버가 꺼져 있거나 다시 시작하는 중입니다. 저장소 루트의 터미널에서 아래 명령을 실행한 뒤 다시
            연결하세요.
          </p>
        </div>
        <div className="command-row">
          <code className="command" translate="no">
            {SERVE_COMMAND}
          </code>
          <CopyButton text={SERVE_COMMAND} label="서버 실행 명령 복사" />
        </div>
        <div className="server-down-actions">
          <button
            type="button"
            className="btn btn-primary"
            onClick={reconnect}
            disabled={retry === 'retrying'}
            aria-busy={retry === 'retrying'}
          >
            {retry === 'retrying' ? '연결하는 중…' : '다시 연결'}
          </button>
          <span className="meta" role="status">
            {retry === 'failed' ? '아직 연결되지 않았습니다. 서버를 실행했는지 확인하세요.' : ''}
          </span>
        </div>
      </div>
    </section>
  );
}
