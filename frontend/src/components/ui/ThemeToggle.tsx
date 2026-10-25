import { useTheme } from '../../app/theme'
import { Button } from './Button'
import { Icon } from './Icon'
export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme()
  return <Button variant="secondary" onClick={toggleTheme} aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`}><Icon name={theme === 'light' ? 'moon' : 'sun'} /><span>{theme === 'light' ? 'Dark' : 'Light'} theme</span></Button>
}
