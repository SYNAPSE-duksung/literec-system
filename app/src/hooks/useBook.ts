import type { Book, HookResult } from '../types';
import { fetchBook } from '../lib/bookCache';
import { useAsyncApi } from './useAsyncApi';

export function useBook(bookId: string): HookResult<Book | null> {
  return useAsyncApi<Book | null>(
    () => (bookId ? fetchBook(bookId) : Promise.resolve(null)),
    [bookId],
    null,
  );
}
