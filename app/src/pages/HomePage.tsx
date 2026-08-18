import { useEffect } from 'react';
import { useBooks } from '../hooks/useBooks';
import { useRecommendations } from '../hooks/useRecommendations';
import { useLogEvent } from '../hooks/useLogEvent';
import { BookCard } from '../components/book/BookCard';
import { XAINote } from '../components/book/XAINote';
import './HomePage.css';

export function HomePage({ onSelectBook }: { onSelectBook: (bookId: string) => void }) {
  const { data: books, isLoading: booksLoading } = useBooks();
  const { data: recommendations, isLoading: recsLoading } = useRecommendations();
  const { logEvent } = useLogEvent();

  const isLoading = booksLoading || recsLoading;

  useEffect(() => {
    if (isLoading) return;
    recommendations.forEach((rec, index) => {
      logEvent({ bookId: rec.bookId, eventType: 'impression', source: 'home', rank: index + 1 });
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoading, recommendations]);

  const handleSelectBook = (bookId: string, rank: number) => {
    logEvent({ bookId, eventType: 'click', source: 'home', rank });
    onSelectBook(bookId);
  };

  return (
    <div className="home-page">
      <p className="home-page__eyebrow">오늘의 추천</p>
      <h2 className="home-page__heading">
        회원님의 결과 닮은
        <br />
        책들을 모아봤어요
      </h2>

      {isLoading && <p className="empty-state">추천을 준비하고 있어요</p>}

      {!isLoading && recommendations.length === 0 && (
        <p className="empty-state">아직 추천할 책이 없어요</p>
      )}

      {!isLoading &&
        recommendations.map((rec, index) => {
          const book = books.find((b) => b.id === rec.bookId);
          if (!book) return null;
          return (
            <BookCard
              key={rec.bookId}
              book={book}
              onClick={() => handleSelectBook(book.id, index + 1)}
            >
              <XAINote text={rec.explanation} />
            </BookCard>
          );
        })}
    </div>
  );
}
