import { CopyButton } from './CopyButton';

/**
 * A repo-relative path in mono with a copy button. It is a link only when the server returned an
 * `href` for it (files outside the static allow-list, such as `.omp/`, would 404).
 */
export function FileLink({ path, href }: { path: string; href: string | null | undefined }) {
  if (!path) return null;
  return (
    <span className="file-link">
      {href ? (
        <a href={href} target="_blank" rel="noopener">
          <code translate="no">{path}</code>
          <span className="visually-hidden"> (새 탭)</span>
        </a>
      ) : (
        <code translate="no">{path}</code>
      )}
      <CopyButton text={path} label={`${path} 경로 복사`} />
    </span>
  );
}
