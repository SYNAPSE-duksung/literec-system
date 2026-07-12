import type { Book, HookResult } from '../types';
import { books } from '../mock/books';
import { useAsyncMock } from './useAsyncMock';

export function useBooks(): HookResult<Book[]> {
  return useAsyncMock(() => books, []);
}
