import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { LucideProvider } from 'lucide-react';
import './fonts';
import './styles/tokens.css';
import './styles/base.css';
import './styles/markdown.css';
import './styles/app.css';
import { App } from './App';
import { ToastProvider } from './components/Toast';
import { MotionProvider } from './motion/MotionProvider';
import { StatusProvider } from './status';

const container = document.getElementById('root');
if (!container) throw new Error('#root element is missing from index.html');

createRoot(container).render(
  <StrictMode>
    <LucideProvider strokeWidth={1.75}>
      <MotionProvider>
        <ToastProvider>
          <StatusProvider>
            <App />
          </StatusProvider>
        </ToastProvider>
      </MotionProvider>
    </LucideProvider>
  </StrictMode>,
);
