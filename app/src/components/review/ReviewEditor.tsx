import { useState } from 'react';
import type { Review } from '../../types';
import { EMOTION_OPTIONS } from '../../constants/options';
import { useCreateReview } from '../../hooks/useCreateReview';
import { ToggleChip } from '../common/ToggleChip';
import { Input } from '../common/Input';
import { Textarea } from '../common/Textarea';
import { PrimaryButton } from '../common/PrimaryButton';
import './ReviewEditor.css';

interface ReviewEditorProps {
  bookId: string;
  onCreated: (review: Review) => void;
}

export function ReviewEditor({ bookId, onCreated }: ReviewEditorProps) {
  const { createReview } = useCreateReview();
  const [emotion, setEmotion] = useState<string[]>([]);
  const [liked, setLiked] = useState('');
  const [disliked, setDisliked] = useState('');
  const [content, setContent] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const toggleEmotion = (value: string) => {
    setEmotion((prev) => (prev.includes(value) ? prev.filter((e) => e !== value) : [...prev, value]));
  };

  const canSubmit = content.trim().length > 0 && !submitting;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    try {
      const review = await createReview({
        bookId,
        content: content.trim(),
        liked: liked.trim() ? [liked.trim()] : [],
        disliked: disliked.trim() ? [disliked.trim()] : [],
        emotion,
      });
      onCreated(review);
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
        기록 올리기
      </PrimaryButton>
    </div>
  );
}
