import { useEffect, useState } from 'react';
import { Button } from './Button';
import { Icon } from './Icon';

export type ThemeMode = 'light' | 'dark';

export function ThemeToggle({ className = '' }: { className?: string }) {
  const [theme, setTheme] = useState<ThemeMode>(() => {
    if (typeof window === 'undefined') return 'dark';
    const saved = localStorage.getItem('cascade-theme') as ThemeMode | null;
    if (saved === 'light' || saved === 'dark') return saved;
    if (typeof window.matchMedia === 'function') {
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    return 'dark';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('cascade-theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  return (
    <Button
      variant="secondary"
      onClick={toggleTheme}
      className={`theme-toggle ${className}`}
      aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
      title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
    >
      <Icon name={theme === 'dark' ? 'sun' : 'moon'} />
      <span>{theme === 'dark' ? 'Light Theme' : 'Dark Theme'}</span>
    </Button>
  );
}

export default ThemeToggle;
