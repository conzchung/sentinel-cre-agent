import type { PlanStep } from '@/lib/types';
import { CheckIcon } from './Icons';

function Marker({ status }: { status: string }) {
  if (status === 'completed') {
    return (
      <span className="pm pm-completed">
        <CheckIcon size={12} />
      </span>
    );
  }
  if (status === 'in_progress') return <span className="pm pm-in_progress" />;
  if (status === 'deleted') return <span className="pm pm-deleted" />;
  return <span className="pm pm-pending" />;
}

// Statuses are authored by the backend: create_plan sets the initial plan,
// update_plan re-emits it with advanced statuses as the agent works, and a final
// terminal <PLAN> marks every non-deleted step completed when the turn ends. The
// frontend stream parser replaces turn.plan on each <PLAN>, so we just render the
// latest snapshot — no client-side progress inference.
export default function PlanBlock({ plan }: { plan: PlanStep[] }) {
  if (!plan.length) return null;
  const total = plan.filter((s) => s.status !== 'deleted').length;
  const done = plan.filter((s) => s.status === 'completed').length;
  return (
    <details className="plan" open>
      <summary>
        <span className="caret">▸</span>
        Plan
        <span className="cnt">
          {done}/{total} step{total === 1 ? '' : 's'}
        </span>
      </summary>
      <ul>
        {plan.map((s, i) => (
          <li key={i} className={s.status === 'deleted' ? 'is-deleted' : ''}>
            <Marker status={s.status} />
            {s.content}
          </li>
        ))}
      </ul>
    </details>
  );
}
