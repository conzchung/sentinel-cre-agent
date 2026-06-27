import type { Action } from '@/lib/types';
import { prettyToolName, toolIconKey } from '@/lib/toolName';
import { ToolGlyph } from './Icons';

export default function ActionChips({ actions }: { actions: Action[] }) {
  if (!actions.length) return null;
  return (
    <details className="actions" open>
      <summary>
        <span className="caret">▸</span>
        Actions
        <span className="cnt">
          {actions.length} step{actions.length === 1 ? '' : 's'}
        </span>
      </summary>
      <div className="actions-list">
        {actions.map((a, i) => (
          <div className="action" key={i} title={a.objective}>
            <span className="ico">
              <ToolGlyph name={toolIconKey(a.tool)} size={15} />
            </span>
            <span className="tool">{prettyToolName(a.tool)}</span>
            {a.objective ? (
              <>
                <span className="sep">·</span>
                <span className="obj">{a.objective}</span>
              </>
            ) : null}
          </div>
        ))}
      </div>
    </details>
  );
}
