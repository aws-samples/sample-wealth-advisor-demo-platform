export type DDStatus = 'pending' | 'in_progress' | 'complete' | 'failed';
export type RAGStatus = 'red' | 'amber' | 'green' | 'grey';
export type Recommendation = 'APPROVE' | 'APPROVE_WITH_CONDITIONS' | 'REJECT';

export interface Portfolio {
  portfolio_id: string;
  name: string;
  manager_id?: string;
  asset_class?: string;
  benchmark?: string;
  aum_aud_m?: number;
}

export interface Session {
  session_id: string;
  portfolio_id: string;
  portfolio_name: string;
  status: DDStatus;
  started_at: string;
  completed_at?: string;
  overall_score?: number;
  recommendation?: Recommendation;
  hitl_required?: boolean;
}

export interface CriterionAssessment {
  criterion_id: string;
  criterion_name?: string;
  category?: string;
  weight?: number;
  confidence?: number;
  score?: number;
  rag_status: RAGStatus;
  summary: string;
  rationale?: string;
  evidence?: string[];
  hitl_required: boolean;
}

export interface CategorySummary {
  category: string;
  weight: number;
  weighted_score: number;
  rag_status: RAGStatus;
}

export interface ReportSection {
  category: string;
  title: string;
  content: string;
  criteria_covered: string[];
}

export interface DDReport {
  report_id: string;
  session_id: string;
  portfolio_id: string;
  overall_score: number;
  overall_rag: RAGStatus;
  category_summaries: CategorySummary[];
  assessments: CriterionAssessment[];
  recommendation: Recommendation;
  narrative: string;
  hitl_required: boolean;
  hitl_reasons: string[];
  generated_at: string;
}

export interface ProgressEvent {
  session_id: string;
  event_type: string;
  criterion_id?: string;
  criterion_name?: string;
  rag_status?: RAGStatus;
  score?: number;
  message: string;
  data?: Record<string, unknown>;
}

export interface HITLFlag {
  flag_id: string;
  criterion_id?: string;
  reason: string;
  status: 'pending' | 'approved' | 'rejected' | 'escalated';
  resolved_at?: string;
  reviewer_notes: string;
}
