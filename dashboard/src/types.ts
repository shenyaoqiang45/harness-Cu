export interface ForecastSignal {
  name: string;
  score: number;
  description: string;
  confidence?: string;
  raw_score?: number;
}

export interface ForecastModule {
  key: string;
  label: string;
  score: number;
  signals: ForecastSignal[];
  data_gaps: string[];
}

export interface CrossValidationGroup {
  name: string;
  label: string;
  score: number;
  direction: string;
  modules: string[];
}

export interface CrossValidation {
  agreement: string;
  note: string;
  groups: CrossValidationGroup[];
}

export interface ForecastAnomaly {
  severity: string;
  indicator: string;
  date: string;
  reason: string;
}

export interface ForecastSnapshot {
  generated_at: string;
  data_cutoff: string | null;
  total_score: number;
  direction: string;
  week_outlook: string;
  month_outlook: string;
  confidence: number;
  data_health: number;
  confidence_note: string;
  low_confidence: boolean;
  modules: ForecastModule[];
  cross_validation: CrossValidation | null;
  supporting_factors: string[];
  suppressing_factors: string[];
  risks: string[];
  invalidation_conditions: string[];
  anomalies: ForecastAnomaly[];
}

export interface HistoryPoint {
  file: string;
  generated_at: string | null;
  total_score: number | null;
  direction: string | null;
  confidence: number | null;
  data_health: number | null;
}
