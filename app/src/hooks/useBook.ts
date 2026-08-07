import type { Book, HookResult } from '../types';
import { books } from '../mock/books';
import { useAsyncMock } from './useAsyncMock';

export function useBook(bookId: string): HookResult<Book | null> {
  return useAsyncMock<Book | null>(
    () => books.find((book) => book.id === bookId) ?? null,
    [bookId],
  );
}
