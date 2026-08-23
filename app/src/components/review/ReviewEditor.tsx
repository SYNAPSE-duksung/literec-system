import { useState } from 'react';
import type { Review } from '../../types';
import { EMOTION_OPTIONS } from '../../constants/options';
import { useCreateReview } from '../../hooks/useCreateReview';
import { useUpdateReview } from '../../hooks/useUpdateReview';
import { ToggleChip } from '../common/ToggleChip';
import { Input } from '../common/Input';
import { Textarea } from '../common/Textarea';
import { PrimaryButton } from '../common/PrimaryButton';
import './ReviewEditor.css';

interface ReviewEditorProps {
  bookId: string;
  // 있으면 수정 모드 — 이 리뷰의 기존 내용으로 폼을 채우고, 제출 시 새로 만들지 않고 이 리뷰를 고친다.
  editingReview?: Review;
  onSaved: (review: Review) => void;
}

export function ReviewEditor({ bookId, editingReview, onSaved }: ReviewEditorProps) {
  const { createReview } = useCreateReview();
  const { updateReview } = useUpdateReview();
  const [emotion, setEmotion] = useState<string[]>(editingReview?.emotion ?? []);
  const [liked, setLiked] = useState(editingReview?.liked[0] ?? '');
  const [disliked, setDisliked] = useState(editingReview?.disliked[0] ?? '');
  const [content, setContent] = useState(editingReview?.content ?? '');
  const [submitting, setSubmitting] = useState(false);

  const toggleEmotion = (value: string) => {
    setEmotion((prev) => (prev.includes(value) ? prev.filter((e) => e !== value) : [...prev, value]));
  };

  const canSubmit = content.trim().length > 0 && !submitting;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    try {
      const input = {
        content: content.trim(),
        liked: liked.trim() ? [liked.trim()] : [],
        disliked: disliked.trim() ? [disliked.trim()] : [],
        emotion,
      };
      const review = editingReview
        ? await updateReview(editingReview.id, input)
        : await createReview({ bookId, ...input });
      onSaved(review);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="review-editor">
      <div className="review-editor__section">
        <p className="review-editor__label">느낀 정서</p>
        <div className="review-editor__chips">
          {EMOTION_OPTIONS.map((option) => (
            <ToggleChip key={option} selected={emotion.includes(option)} onToggle={() => toggleEmotion(option)}>
              {option}
            </ToggleChip>
          ))}
        </div>
      </div>

      <Input
        id="review-editor-liked"
        label="좋았던 점"
        value={liked}
        onChange={(e) => setLiked(e.target.value)}
      />
      <Input
        id="review-editor-disliked"
        label="아쉬웠던 점"
        value={disliked}
        onChange={(e) => setDisliked(e.target.value)}
      />
      <Textarea
        id="review-editor-content"
        label="기록"
        rows={7}
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="이 책에 대한 기록을 남겨보세요"
      />

      <PrimaryButton disabled={!canSubmit} onClick={handleSubmit}>
        {editingReview ? '수정 완료' : '기록 올리기'}
      </PrimaryButton>
    </div>
  );
}
