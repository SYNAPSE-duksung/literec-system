import type { Book, HookResult } from '../types';
import { fetchBooks } from '../lib/bookCache';
import { useAsyncApi } from './useAsyncApi';

export function useBooks(): HookResult<Book[]> {
  return useAsyncApi(() => fetchBooks(), [], []);
}
