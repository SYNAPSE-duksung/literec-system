import { apiFetch } from '../lib/apiClient';

export interface UseDeleteAccountResult {
  deleteAccount: () => Promise<void>;
}

export function useDeleteAccount(): UseDeleteAccountResult {
  const deleteAccount = (): Promise<void> => apiFetch<void>('/api/users/me', { method: 'DELETE' });

  return { deleteAccount };
}
