export type PlanStatus = 'pending' | 'in_progress' | 'completed' | 'deleted';

export interface PlanStep {
  content: string;
  status: PlanStatus;
  remarks?: string | null;
}

export interface Action {
  tool: string;
  objective: string;
}

export interface Turn {
  role: 'user' | 'assistant';
  text: string;
  plan: PlanStep[];
  actions: Action[];
  charts: string[]; // raw Plotly figure JSON strings
  suggestions: string[];
}

export interface Conversation {
  thread_id: string;
  convo_title: string | null;
  updated_at: string | null;
}

export type ToolIconKey =
  | 'skill'
  | 'data'
  | 'chart'
  | 'web'
  | 'knowledge'
  | 'report'
  | 'plan'
  | 'tool';
