import { useState } from 'react';
import { useBook } from '../hooks/useBook';
import { useBooks } from '../hooks/useBooks';
import { useReview } from '../hooks/useReview';
import { ReviewEditor } from '../components/review/ReviewEditor';
import { BookCard } from '../components/book/BookCard';
import { Card } from '../components/common/Card';
import { Input } from '../components/common/Input';
import { Button } from '../components/common/Button';
import type { Review } from '../types';
import './ReviewWritePage.css';

interface ReviewWritePageProps {
  bookId: string;
  // 있으면 수정 모드 — 이 리뷰를 새로 만들지 않고 고친다(책 선택은 비활성화).
  reviewId?: string;
  onSaved: (reviewId: string) => void;
}

export function ReviewWritePage({ bookId: initialBookId, reviewId, onSaved }: ReviewWritePageProps) {
  const isEditing = Boolean(reviewId);
  const canChangeBook = !initialBookId && !isEditing;
  const [selectedBookId, setSelectedBookId] = useState(initialBookId);
  const [query, setQuery] = useState('');

  const { data: book } = useBook(selectedBookId);
  const { data: allBooks } = useBooks();
  const { data: editingReview, isLoading: editingReviewLoading } = useReview(reviewId ?? '');

  const handleSaved = (review: Review) => {
    onSaved(review.id);
  };

  if (isEditing && editingReviewLoading) {
    return <div className="review-write-page empty-state">불러오는 중이에요</div>;
  }

  if (!selectedBookId) {
    const filtered = allBooks.filter(
      (b) =>
        b.title.toLowerCase().includes(query.toLowerCase()) ||
        b.author.toLowerCase().includes(query.toLowerCase()),
    );

    return (
      <div className="review-write-page">
        <p className="review-write-page__section-title">어떤 책에 대한 기록인가요?</p>
        <Input
          id="review-write-book-search"
          autoFocus
          placeholder="제목 또는 작가를 검색해보세요"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {query.trim() && filtered.length === 0 && <p className="empty-state">검색 결과가 없어요</p>}
        <div className="review-write-page__book-list">
          {filtered.map((b) => (
            <BookCard
              key={b.id}
              book={b}
              onClick={() => setSelectedBookId(b.id)}
              showLikeButton={false}
            />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="review-write-page">
      {book && (
        <Card className="review-write-page__book">
          <img
            className="review-write-page__cover"
            src={book.coverUrl}
            alt={book.title}
            decoding="async"
          />
          <div>
            <p className="review-write-page__title">{book.title}</p>
            <p className="review-write-page__author">
              {book.author} · {book.publisher}
            </p>
          </div>
        </Card>
      )}

      {canChangeBook && (
        <Button variant="text" onClick={() => setSelectedBookId('')}>
          다른 책 선택
        </Button>
      )}

      <ReviewEditor
        bookId={selectedBookId}
        editingReview={editingReview ?? undefined}
        onSaved={handleSaved}
      />
    </div>
  );
}
