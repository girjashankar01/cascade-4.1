import { ThemeProvider } from './app/ThemeProvider'
import { StyleTilePage } from './pages/StyleTilePage'

function App() {
  // Temporary Stage 1 review surface; routing belongs to Stage 2.
  return <ThemeProvider defaultTheme="light"><StyleTilePage /></ThemeProvider>
}

export default App
