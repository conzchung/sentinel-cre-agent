import type { Turn } from '@/lib/types';
import PlanBlock from './PlanBlock';
import ActionChips from './ActionChips';
import AnswerMarkdown from './AnswerMarkdown';
import ChartView from './ChartView';

export default function AssistantTurn({
  turn,
  streaming = false,
}: {
  turn: Turn;
  streaming?: boolean;
}) {
  // Nothing has arrived yet on a live turn → show the working/loading state.
  const isEmpty =
    !turn.text &&
    turn.plan.length === 0 &&
    turn.actions.length === 0 &&
    turn.charts.length === 0;
  const showLoading = streaming && isEmpty;

  return (
    <div className="turn turn-asst">
      <div className="asst-rail">
        <span className={`asst-dot ${streaming ? 'live' : ''}`} />
      </div>
      <div className="asst-body">
        {showLoading ? (
          <>
            <div className="thinking">
              <span className="dot" />
              <span className="dot" />
              <span className="dot" />
              <em>Working…</em>
            </div>
            <div className="skeleton">
              <div className="shimmer w1" />
              <div className="shimmer w2" />
              <div className="shimmer w3" />
            </div>
          </>
        ) : (
          <>
            <PlanBlock plan={turn.plan} />
            <ActionChips actions={turn.actions} />
            <AnswerMarkdown text={turn.text} streaming={streaming} />
            {/* The backend buffers <CHART> payloads and flushes them only after
                the </RESPONSE> block closes (run_agent), so charts always arrive
                below fully-streamed prose and are never stranded above an empty
                answer. We can therefore render them as soon as they appear. */}
            {turn.charts.map((c, i) => <ChartView key={i} figureJson={c} />)}
          </>
        )}
      </div>
    </div>
  );
}
