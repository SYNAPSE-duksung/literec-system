import type { HookResult, Recommendation } from '../types';
import { apiFetch } from '../lib/apiClient';
import { useAsyncApi } from './useAsyncApi';

export function useRecommendations(): HookResult<Recommendation[]> {
  return useAsyncApi(() => apiFetch<Recommendation[]>('/api/recommendations'), [], []);
}
