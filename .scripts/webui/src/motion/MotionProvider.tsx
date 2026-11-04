import type { ReactNode } from 'react';
import { LazyMotion, MotionConfig } from 'motion/react';

const loadFeatures = () => import('./features').then((module) => module.default);

/**
 * App-wide motion setup. `reducedMotion="user"` drops transform and layout animation (opacity
 * stays) when the OS asks for reduced motion. `strict` makes any full `motion.*` component throw:
 * components use `import * as m from 'motion/react-m'` only.
 */
export function MotionProvider({ children }: { children: ReactNode }) {
  return (
    <MotionConfig reducedMotion="user">
      <LazyMotion strict features={loadFeatures}>
        {children}
      </LazyMotion>
    </MotionConfig>
  );
}
