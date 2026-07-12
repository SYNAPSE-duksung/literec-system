import { useState } from 'react';
import { EMOTION_OPTIONS, AVOIDED_TRAIT_OPTIONS } from '../constants/options';
import { useUserProfile } from '../hooks/useUserProfile';
import { ToggleChip } from '../components/common/ToggleChip';
import { PrimaryButton } from '../components/common/PrimaryButton';
import './OnboardingPage.css';

export function OnboardingPage({ onComplete }: { onComplete: () => void }) {
  const { updateProfile } = useUserProfile();
  const [step, setStep] = useState(1);
  const [preferredEmotions, setPreferredEmotions] = useState<string[]>([]);
  const [avoidedTraits, setAvoidedTraits] = useState<string[]>([]);

  const toggle = (list: string[], setList: (v: string[]) => void, value: string) => {
    setList(list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
  };

  const handleFinish = () => {
    updateProfile({ preferredEmotions, avoidedTraits });
    onComplete();
  };

  return (
    <div className="onboarding-page">
      <div className="onboarding-page__progress">
        <div className={`onboarding-page__bar ${step >= 1 ? 'onboarding-page__bar--filled' : ''}`} />
        <div className={`onboarding-page__bar ${step >= 2 ? 'onboarding-page__bar--filled' : ''}`} />
      </div>

      {step === 1 && (
        <div className="onboarding-page__step">
          <h2 className="onboarding-page__title">어떤 정서를 좋아하세요?</h2>
          <div className="onboarding-page__chips">
            {EMOTION_OPTIONS.map((option) => (
              <ToggleChip
                key={option}
                selected={preferredEmotions.includes(option)}
                onToggle={() => toggle(preferredEmotions, setPreferredEmotions, option)}
              >
                {option}
              </ToggleChip>
            ))}
          </div>
          <PrimaryButton disabled={preferredEmotions.length === 0} onClick={() => setStep(2)}>
            다음
          </PrimaryButton>
        </div>
      )}

      {step === 2 && (
        <div className="onboarding-page__step">
          <h2 className="onboarding-page__title">부담스러운 요소가 있나요?</h2>
          <div className="onboarding-page__chips">
            {AVOIDED_TRAIT_OPTIONS.map((option) => (
              <ToggleChip
                key={option}
                selected={avoidedTraits.includes(option)}
                onToggle={() => toggle(avoidedTraits, setAvoidedTraits, option)}
              >
                {option}
              </ToggleChip>
            ))}
          </div>
          <PrimaryButton onClick={handleFinish}>완료하고 추천 받기</PrimaryButton>
        </div>
      )}
    </div>
  );
}
