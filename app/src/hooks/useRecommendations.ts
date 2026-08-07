import type { HookResult, Recommendation } from '../types';
import { recommendations } from '../mock/recommendations';
import { useAsyncMock } from './useAsyncMock';

export function useRecommendations(): HookResult<Recommendation[]> {
  return useAsyncMock(() => recommendations, []);
}
