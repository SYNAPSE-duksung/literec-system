import { clearAuth, getAccessToken, setAccessToken } from './authToken';

export interface ApiError extends Error {
  status: number;
}

function buildError(status: number, message: string): ApiError {
  const error = new Error(message) as ApiError;
  error.status = status;
  return error;
}

// access token 만료로 401을 받으면 이 콜백으로 App에 알려 로그인 화면으로 되돌아가게 한다.
let onAuthExpired: (() => void) | null = null;

export function registerAuthExpiredHandler(handler: (() => void) | null): void {
  onAuthExpired = handler;
}

// 동시에 여러 요청이 401을 맞아도 refresh 호출은 한 번만 나가도록 in-flight 요청을 공유한다.
let refreshPromise: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = fetch('/api/auth/refresh', { method: 'POST', credentials: 'include' })
      .then(async (res) => {
        if (!res.ok) return false;
        const body = (await res.json()) as { access_token: string };
        setAccessToken(body.access_token);
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
  _isRetry = false,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has('Content-Type') && init.body) {
    headers.set('Content-Type', 'application/json');
  }
  const token = getAccessToken();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const res = await fetch(path, { ...init, headers, credentials: 'include' });

  const isAuthEndpoint = path === '/api/auth/refresh' || path === '/api/auth/login';
  if (res.status === 401 && !_isRetry && !isAuthEndpoint) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return apiFetch<T>(path, init, true);
    }
    clearAuth();
    onAuthExpired?.();
    throw buildError(401, '인증이 만료되었습니다. 다시 로그인해주세요.');
  }

  if (!res.ok) {
    throw buildError(res.status, `요청이 실패했습니다. (${res.status})`);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return (await res.json()) as T;
}
