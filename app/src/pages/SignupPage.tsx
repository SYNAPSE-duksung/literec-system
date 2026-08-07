import { useState } from 'react';
import { Input } from '../components/common/Input';
import { PrimaryButton } from '../components/common/PrimaryButton';
import { Button } from '../components/common/Button';
import { BackIcon } from '../icons';
import './SignupPage.css';

const EMAIL_PATTERN = /\S+@\S+\.\S+/;

export interface SignupInput {
  name: string;
  email: string;
  password: string;
}

interface SignupPageProps {
  onSignupComplete: (input: SignupInput) => Promise<void>;
  onBack: () => void;
}

export function SignupPage({ onSignupComplete, onBack }: SignupPageProps) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const emailValid = email.length === 0 || EMAIL_PATTERN.test(email);
  const passwordsMatch = confirmPassword.length === 0 || password === confirmPassword;

  const canSubmit =
    name.trim().length > 0 &&
    EMAIL_PATTERN.test(email) &&
    password.length > 3 &&
    password === confirmPassword &&
    !submitting;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setError(null);
    setSubmitting(true);
    try {
      await onSignupComplete({ name: name.trim(), email, password });
    } catch {
      setError('이미 가입된 이메일이거나 요청을 처리할 수 없어요');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="signup-page">
      <button type="button" className="signup-page__back" onClick={onBack} aria-label="뒤로가기">
        <BackIcon width={20} height={20} />
      </button>

      <h1 className="signup-page__title">회원가입</h1>
      <p className="signup-page__subtitle">몇 가지 정보만 알려주세요</p>

      <div className="signup-page__form">
        <Input id="signup-name" label="이름" value={name} onChange={(e) => setName(e.target.value)} />
        <Input
          id="signup-email"
          label="이메일"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={!emailValid ? '올바른 이메일 형식이 아니에요' : undefined}
        />
        <Input
          id="signup-password"
          label="비밀번호"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <Input
          id="signup-confirm-password"
          label="비밀번호 확인"
          type="password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          error={!passwordsMatch ? '비밀번호가 일치하지 않아요' : undefined}
        />
        {error && <p className="signup-page__error">{error}</p>}
      </div>

      <PrimaryButton disabled={!canSubmit} onClick={handleSubmit}>
        가입하고 시작하기
      </PrimaryButton>

      <Button variant="text" onClick={onBack}>
        이미 계정이 있으신가요? 로그인
      </Button>
    </div>
  );
}
