import { useState } from 'react';
import type { MyListType } from '../types';
import { useUserProfile } from '../hooks/useUserProfile';
import { useBooks } from '../hooks/useBooks';
import { useReviews } from '../hooks/useReviews';
import { Avatar } from '../components/common/Avatar';
import { Button } from '../components/common/Button';
import { ToggleChip } from '../components/common/ToggleChip';
import { BookCard } from '../components/book/BookCard';
import { ReviewCard } from '../components/review/ReviewCard';
import { EMOTION_OPTIONS, AVOIDED_TRAIT_OPTIONS } from '../constants/options';
import './MyPage.css';

const PREVIEW_LIMIT = 3;

interface MyPageProps {
  accountId: string;
  onSelectBook: (bookId: string) => void;
  onSelectReview: (reviewId: string) => void;
  onViewAll: (listType: MyListType) => void;
  onLogout: () => void;
}

export function MyPage({ accountId, onSelectBook, onSelectReview, onViewAll, onLogout }: MyPageProps) {
  const { data: profile, dislikedBookIds, updateProfile } = useUserProfile();
  const { data: books } = useBooks();
  const { data: reviews } = useReviews();
  const [editingEmotions, setEditingEmotions] = useState(false);
  const [draftEmotions, setDraftEmotions] = useState<string[]>([]);
  const [editingAvoided, setEditingAvoided] = useState(false);
  const [draftAvoided, setDraftAvoided] = useState<string[]>([]);

  const likedBooks = books.filter((book) => profile?.likedBookIds.includes(book.id));
  const dislikedBooks = books.filter((book) => dislikedBookIds.includes(book.id));
  const myReviews = reviews.filter((review) => review.userId === profile?.userId);
  const hasPreferredEmotions = (profile?.preferredEmotions.length ?? 0) > 0;
  const hasAvoidedTraits = (profile?.avoidedTraits.length ?? 0) > 0;

  const startEditingEmotions = () => {
    setDraftEmotions(profile?.preferredEmotions ?? []);
    setEditingEmotions(true);
  };

  const toggleDraftEmotion = (value: string) => {
    setDraftEmotions((prev) =>
      prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value],
    );
  };

  const saveEmotions = () => {
    updateProfile({ preferredEmotions: draftEmotions });
    setEditingEmotions(false);
  };

  const startEditingAvoided = () => {
    setDraftAvoided(profile?.avoidedTraits ?? []);
    setEditingAvoided(true);
  };

  const toggleDraftAvoided = (value: string) => {
    setDraftAvoided((prev) =>
      prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value],
    );
  };

  const saveAvoided = () => {
    updateProfile({ avoidedTraits: draftAvoided });
    setEditingAvoided(false);
  };

  return (
    <div className="mypage">
      <div className="mypage__profile">
        <Avatar name="나" />
        <div className="mypage__profile-info">
          <p className="mypage__name">나</p>
          <p className="mypage__account-id">{accountId}</p>
          {!editingEmotions && (
            <div className="mypage__preferences-row">
              <p className="mypage__preferences">
                {hasPreferredEmotions
                  ? profile!.preferredEmotions.join(', ')
                  : '선호 정서를 아직 설정하지 않았어요'}
              </p>
              <Button
                variant="text"
                className="mypage__preferences-edit-btn"
                onClick={startEditingEmotions}
              >
                {hasPreferredEmotions ? '수정' : '선택하기'}
              </Button>
            </div>
          )}
          {!editingAvoided && (
            <div className="mypage__preferences-row">
              <p className="mypage__preferences">
                {hasAvoidedTraits
                  ? `피하고 싶은 요소: ${profile!.avoidedTraits.join(', ')}`
                  : '피하고 싶은 요소를 설정하지 않았어요'}
              </p>
              <Button
                variant="text"
                className="mypage__preferences-edit-btn"
                onClick={startEditingAvoided}
              >
                {hasAvoidedTraits ? '수정' : '선택하기'}
              </Button>
            </div>
          )}
        </div>
        <Button variant="text" className="mypage__logout-btn" onClick={onLogout}>
          로그아웃
        </Button>
      </div>

      {editingEmotions && (
        <div className="mypage__emotions-editor">
          <p className="mypage__emotions-editor-title">어떤 정서를 좋아하세요?</p>
          <div className="mypage__chips">
            {EMOTION_OPTIONS.map((option) => (
              <ToggleChip
                key={option}
                selected={draftEmotions.includes(option)}
                onToggle={() => toggleDraftEmotion(option)}
              >
                {option}
              </ToggleChip>
            ))}
          </div>
          <div className="mypage__emotions-editor-actions">
            <Button variant="text" onClick={() => setEditingEmotions(false)}>
              취소
            </Button>
            <Button
              variant="primary"
              className="mypage__emotions-save-btn"
              disabled={draftEmotions.length === 0}
              onClick={saveEmotions}
            >
              저장
            </Button>
          </div>
        </div>
      )}

      {editingAvoided && (
        <div className="mypage__emotions-editor">
          <p className="mypage__emotions-editor-title">부담스러운 요소가 있나요?</p>
          <div className="mypage__chips">
            {AVOIDED_TRAIT_OPTIONS.map((option) => (
              <ToggleChip
                key={option}
                selected={draftAvoided.includes(option)}
                onToggle={() => toggleDraftAvoided(option)}
              >
                {option}
              </ToggleChip>
            ))}
          </div>
          <div className="mypage__emotions-editor-actions">
            <Button variant="text" onClick={() => setEditingAvoided(false)}>
              취소
            </Button>
            <Button
              variant="primary"
              className="mypage__emotions-save-btn"
              onClick={saveAvoided}
            >
              저장
            </Button>
          </div>
        </div>
      )}

      <div className="mypage__section-header">
        <p className="mypage__section-title">좋아한 책 {likedBooks.length}개</p>
        {likedBooks.length > PREVIEW_LIMIT && (
          <Button variant="text" onClick={() => onViewAll('likedBooks')}>
            전체 보기
          </Button>
        )}
      </div>
      {likedBooks.length === 0 && <p className="empty-state">아직 좋아한 책이 없어요</p>}
      {likedBooks.slice(0, PREVIEW_LIMIT).map((book) => (
        <BookCard key={book.id} book={book} onClick={() => onSelectBook(book.id)} />
      ))}

      <div className="mypage__section-header">
        <p className="mypage__section-title">싫어요 표시한 책 {dislikedBooks.length}개</p>
        {dislikedBooks.length > PREVIEW_LIMIT && (
          <Button variant="text" onClick={() => onViewAll('dislikedBooks')}>
            전체 보기
          </Button>
        )}
      </div>
      {dislikedBooks.length === 0 && <p className="empty-state">아직 싫어요 표시한 책이 없어요</p>}
      {dislikedBooks.slice(0, PREVIEW_LIMIT).map((book) => (
        <BookCard key={book.id} book={book} onClick={() => onSelectBook(book.id)} />
      ))}

      <div className="mypage__section-header">
        <p className="mypage__section-title">내가 남긴 기록 {myReviews.length}개</p>
        {myReviews.length > PREVIEW_LIMIT && (
          <Button variant="text" onClick={() => onViewAll('myReviews')}>
            전체 보기
          </Button>
        )}
      </div>
      {myReviews.length === 0 && <p className="empty-state">아직 남긴 기록이 없어요</p>}
      {myReviews.slice(0, PREVIEW_LIMIT).map((review) => (
        <ReviewCard key={review.id} review={review} onClick={() => onSelectReview(review.id)} />
      ))}
    </div>
  );
}
