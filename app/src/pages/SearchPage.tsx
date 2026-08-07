import { useState } from 'react';
import { useBooks } from '../hooks/useBooks';
import { BookCard } from '../components/book/BookCard';
import { Input } from '../components/common/Input';
import './SearchPage.css';

export function SearchPage({ onSelectBook }: { onSelectBook: (bookId: string) => void }) {
  const { data: books, isLoading } = useBooks();
  const [query, setQuery] = useState('');

  const filtered = books.filter(
    (book) =>
      book.title.toLowerCase().includes(query.toLowerCase()) ||
      book.author.toLowerCase().includes(query.toLowerCase()),
  );

  return (
    <div className="search-page">
      <Input
        id="search-query"
        autoFocus
        placeholder="제목 또는 작가를 검색해보세요"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />

      {!isLoading && query.trim() && filtered.length === 0 && (
        <p className="empty-state">검색 결과가 없어요</p>
      )}

      <div className="search-page__list">
        {filtered.map((book) => (
          <BookCard key={book.id} book={book} onClick={() => onSelectBook(book.id)} />
        ))}
      </div>
    </div>
  );
}
