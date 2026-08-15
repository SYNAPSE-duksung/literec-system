import type { Book } from '../types';
import { apiFetch } from './apiClient';

// 책 데이터는 시드 이후 바뀌지 않으므로(수정 API 없음) 세션 동안 무기한 캐시해도 안전하다.
// ReviewCard처럼 리스트 하나에 같은 책을 여러 번 참조하는 곳에서 매번 개별
// GET /api/books/{isbn}을 쏘면 리뷰 수만큼 요청이 폭증하므로, 전체 목록 한 번으로
// 캐시를 채우고 이후 조회는 전부 여기서 즉시 반환한다.
const cache = new Map<string, Book>();
let allBooksPromise: Promise<Book[]> | null = null;

function loadAllBooks(): Promise<Book[]> {
  if (!allBooksPromise) {
    allBooksPromise = apiFetch<Book[]>('/api/books').then((books) => {
      for (const book of books) cache.set(book.id, book);
      return books;
    });
  }
  return allBooksPromise;
}

export function fetchBooks(): Promise<Book[]> {
  return loadAllBooks();
}

export async function fetchBook(bookId: string): Promise<Book | null> {
  const cached = cache.get(bookId);
  if (cached) return cached;
  const books = await loadAllBooks();
  return books.find((b) => b.id === bookId) ?? null;
}
