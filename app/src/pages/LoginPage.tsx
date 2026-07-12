import { useState } from 'react';
import { Input } from '../components/common/Input';
import { PrimaryButton } from '../components/common/PrimaryButton';
import { Button } from '../components/common/Button';
import './LoginPage.css';

interface LoginPageProps {
  onLogin: () => void;
  onGoSignup: () => void;
}

export function LoginPage({ onLogin, onGoSignup }: LoginPageProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const canSubmit = email.length > 3 && password.length > 3;

  return (
    <div className="login-page">
      <h1 className="login-page__logo">결</h1>
      <p className="login-page__tagline">깊이 있는 후기로 책을 만나요</p>

      <div className="login-page__form">
        <Input
          id="login-email"
          label="이메일"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Input
          id="login-password"
          label="비밀번호"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>

      <PrimaryButton disabled={!canSubmit} onClick={onLogin}>
        로그인
      </PrimaryButton>

      <Button variant="text" onClick={onGoSignup}>
        계정이 없으신가요? 회원가입
      </Button>
    </div>
  );
}
