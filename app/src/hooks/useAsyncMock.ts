import { useEffect, useState } from 'react';
import type { HookResult } from '../types';

export function useAsyncMock<T>(factory: () => T, deps: unknown[], delay = 300): HookResult<T> {
  const [data, setData] = useState<T>(factory);
  const [isLoading, setIsLoading] = useState(true);
  const [isError] = useState(false);

  useEffect(() => {
    setIsLoading(true);
    const timer = setTimeout(() => {
      setData(factory());
      setIsLoading(false);
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, delay);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, isLoading, isError };
}
