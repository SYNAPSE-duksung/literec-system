import type { MyListType } from '../types';
import { useUserProfile } from '../hooks/useUserProfile';
import { useBooks } from '../hooks/useBooks';
import { useReviews } from '../hooks/useReviews';
import { CURRENT_USER_ID } from '../constants/user';
import { BookCard } from '../components/book/BookCard';
import { ReviewCard } from '../components/review/ReviewCard';
import './MyListPage.css';

interface MyListPageProps {
  listType: MyListType;
  onSelectBook: (bookId: string) => void;
  onSelectReview: (reviewId: string) => void;
}

const EMPTY_TEXT: Record<MyListType, string> = {
  likedBooks: '아직 좋아한 책이 없어요',
  dislikedBooks: '아직 싫어요 표시한 책이 없어요',
  myReviews: '아직 남긴 기록이 없어요',
};

export function MyListPage({ listType, onSelectBook, onSelectReview }: MyListPageProps) {
  const { data: profile, dislikedBookIds } = useUserProfile();
  const { data: books } = useBooks();
  const { data: reviews } = useReviews();

  if (listType === 'myReviews') {
    const myReviews = reviews.filter((review) => review.userId === CURRENT_USER_ID);
    return (
      <div className="my-list-page">
        {myReviews.length === 0 && <p className="empty-state">{EMPTY_TEXT[listType]}</p>}
        {myReviews.map((review) => (
          <ReviewCard key={review.id} review={review} onClick={() => onSelectReview(review.id)} />
        ))}
      </div>
    );
  }

  const bookIds = listType === 'likedBooks' ? (profile?.likedBookIds ?? []) : dislikedBookIds;
  const list = books.filter((book) => bookIds.includes(book.id));

  return (
    <div className="my-list-page">
      {list.length === 0 && <p className="empty-state">{EMPTY_TEXT[listType]}</p>}
      {list.map((book) => (
        <BookCard key={book.id} book={book} onClick={() => onSelectBook(book.id)} />
      ))}
    </div>
  );
}
