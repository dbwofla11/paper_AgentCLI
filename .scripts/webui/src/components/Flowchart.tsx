import { Fragment, memo, useId, useMemo, useState } from 'react';
import { ArrowDown } from 'lucide-react';
import { orderFlowchart, parseFlowchart } from '../markdown/flowchart';

/** Branch targets show the first line of their label, shortened. */
const TARGET_PREVIEW = 36;

function preview(label: string): string {
  const line = label.split('\n')[0];
  return line.length > TARGET_PREVIEW ? `${line.slice(0, TARGET_PREVIEW)}…` : line;
}

function Lines({ text }: { text: string }) {
  return (
    <>
      {text.split('\n').map((line, index) => (
        <Fragment key={index}>
          {index > 0 ? <br /> : null}
          {line}
        </Fragment>
      ))}
    </>
  );
}

/**
 * A Mermaid `flowchart` block as an ordered chain of numbered steps. The edge to the following
 * step is drawn as an arrow with its label; other edges are listed as "→ N · M". Unparsable
 * blocks fall back to the source as a code block. Shared by the reader and the harness sheet.
 */
export const Flowchart = memo(function Flowchart({ source }: { source: string }) {
  const steps = useMemo(() => {
    const chart = parseFlowchart(source);
    return chart ? orderFlowchart(chart) : [];
  }, [source]);
  const [showSource, setShowSource] = useState(false);
  const sourceId = useId();

  if (steps.length === 0) {
    return (
      <pre>
        <code className="language-mermaid">{source}</code>
      </pre>
    );
  }

  return (
    <figure className="flow" role="figure" aria-label="방법 구조도">
      <ol className="flow-steps" role="list">
        {steps.map((step, index) => (
          <li className="flow-step" key={step.node.id}>
            <div className="flow-node">
              <span className="flow-index num" aria-hidden="true">
                {index + 1}
              </span>
              <div className="flow-body">
                <p className="flow-label">
                  <Lines text={step.node.label} />
                </p>
                {step.branches.length > 0 ? (
                  <p className="flow-branches">
                    <span className="visually-hidden">다른 연결: </span>
                    {step.branches.map(({ edge, target }, branchIndex) => (
                      <Fragment key={`${edge.to}:${branchIndex}`}>
                        {branchIndex > 0 ? <span aria-hidden="true"> · </span> : null}
                        <span className="flow-branch">
                          <span className="flow-ref num">
                            {target === index ? '↻' : '→'} {target + 1}
                          </span>{' '}
                          <span className="flow-branch-target">
                            {target === index ? '같은 단계로 되돌아감' : preview(steps[target].node.label)}
                          </span>
                          {edge.label ? <span className="flow-edge-label">{edge.label}</span> : null}
                        </span>
                      </Fragment>
                    ))}
                  </p>
                ) : null}
              </div>
            </div>
            {step.next ? (
              <div className="flow-link">
                <ArrowDown />
                {step.next.label ? <span className="flow-edge-label">{step.next.label}</span> : null}
              </div>
            ) : null}
          </li>
        ))}
      </ol>
      <div className="flow-foot">
        <button
          type="button"
          className="btn btn-text btn-small"
          aria-expanded={showSource}
          aria-controls={sourceId}
          onClick={() => setShowSource((shown) => !shown)}
        >
          {showSource ? '원문 숨기기' : '원문 보기'}
        </button>
      </div>
      <pre id={sourceId} className="flow-source" hidden={!showSource}>
        <code translate="no">{source}</code>
      </pre>
    </figure>
  );
});
