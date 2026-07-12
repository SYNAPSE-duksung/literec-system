import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { MockStoreProvider } from './state/MockStoreContext';
import { App } from './App';
import './styles/tokens.css';
import './styles/app.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MockStoreProvider>
      <App />
    </MockStoreProvider>
  </StrictMode>,
);
