import { useEffect, useState } from 'react'
import { Button } from '../components/ui/Button'
import { Icon } from '../components/ui/Icon'
import { StatusMark } from '../components/ui/StatusMark'
import { ThemeToggle } from '../components/ui/ThemeToggle'
import { LazyLock } from '../components/lock/LazyLock'
import './StyleTilePage.css'

const swatches = [
  { name: 'Canvas', description: 'Room to think', token: 'canvas' },
  { name: 'Ink', description: 'A clear hierarchy', token: 'ink' },
  { name: 'Quiet', description: 'Supporting detail', token: 'quiet' },
  { name: 'Amber', description: 'A deliberate action', token: 'amber' },
  { name: 'Allowed', description: 'Matches the plan', token: 'allowed' },
  { name: 'Blocked', description: 'A change was stopped', token: 'blocked' },
]

export function StyleTilePage() {
  const [engaged, setEngaged] = useState(false)
  const [selected, setSelected] = useState('valid')
  const [reducePreviewMotion, setReducePreviewMotion] = useState(false)
  useEffect(() => () => { delete document.documentElement.dataset.reduceMotion }, [])
  function resetPreview() { setEngaged(false); setSelected('valid') }
  return (
    <>
      <a className="skip-link" href="#main">Skip to content</a>
      <div className="style-page">
        <header className="site-header">
          <a className="brand" href="/style-tile" aria-label="DAO Accountability Engine design preview"><Icon name="lock" /><span>DAO Accountability<br className="brand-break" /> Engine</span></a>
          <div className="header-actions"><span className="review-label">Design foundations</span><ThemeToggle /></div>
        </header>
        <main id="main" tabIndex={-1}>
          <section className="foundation-intro" aria-labelledby="page-title">
            <div className="intro-copy">
              <h1 id="page-title">Clear intent.<br />A solid lock.</h1>
              <p className="intro-description">A calm place to understand a payment. A solid lock to hold it to the approved plan.</p>
              <div className="intro-note"><span className="note-line" aria-hidden="true" /><p>Style tile for review.<br />Preview controls only. No payment runs here.</p></div>
              <a className="text-link" href="#foundations">Explore the foundations <Icon name="arrow" /></a>
            </div>
            <figure className="lock-exhibit">
              <div className="exhibit-label"><span>The signature object</span><span>Interactive preview</span></div>
              <LazyLock engaged={engaged} />
              <figcaption className="lock-caption">
                <div className="lock-state" role="status" aria-live="polite"><Icon name={engaged ? 'lock' : 'unlock'} /><span>{engaged ? 'Lock engaged' : 'Ready to engage'}</span></div>
                <p>{engaged ? 'The approved plan is held in place.' : 'One clear movement. One visible state.'}</p>
              </figcaption>
              <Button className="lock-action" onClick={() => setEngaged(!engaged)}>{engaged ? 'Release the lock' : 'Engage the lock'}<Icon name="arrow" /></Button>
              <label className="motion-choice"><input type="checkbox" checked={reducePreviewMotion} onChange={event => { document.documentElement.dataset.reduceMotion = String(event.target.checked); setReducePreviewMotion(event.target.checked) }} />Reduce preview motion</label>
            </figure>
          </section>
          <section id="foundations" className="foundation-section palette-section" aria-labelledby="palette-title">
            <div className="section-heading"><h2 id="palette-title">Quiet by default.<br />Clear when it counts.</h2><p>Neutral surfaces carry the story. Amber invites an action. Green and red have one job: explain the outcome.</p></div>
            <div className="swatches">{swatches.map(swatch => <figure className={`swatch swatch--${swatch.token}`} key={swatch.token}><div className="swatch-color" aria-hidden="true"><span className="swatch-marker" /></div><figcaption><h3>{swatch.name}</h3><p>{swatch.description}</p></figcaption></figure>)}</div>
          </section>
          <section className="foundation-section type-section" aria-labelledby="type-title">
            <div className="type-caption"><h2 id="type-title">Words with room<br />to breathe.</h2><p>Space Grotesk gives the story a voice. Source Sans 3 keeps the details easy to read.</p><span className="type-meta">Display &amp; reading</span></div>
            <div className="type-specimen"><p className="specimen-display" aria-label="Display font specimen: The plan holds firm.">The plan<br />holds firm.</p><p className="specimen-body">The payment you approved should be the payment that gets sent. See the recipient, the amount, and what changed, in words you can act on.</p><p className="specimen-numbers" aria-label="Number specimen">0123456789 <span>Aa Bb Cc</span></p></div>
          </section>
          <section className="foundation-section controls-section" aria-labelledby="controls-title">
            <div className="section-heading"><h2 id="controls-title">A choice should<br />feel like a choice.</h2><p>Readable labels. A clear selected state. Controls that work with a mouse, a keyboard, or a touch.</p></div>
            <fieldset className="scenario-choices"><legend className="choices-legend">Example choices <span>Demo data · test tokens</span></legend>
              <label className={`scenario-choice ${selected === 'valid' ? 'is-selected' : ''}`}><input type="radio" name="example-scenario" value="valid" checked={selected === 'valid'} onChange={() => setSelected('valid')} /><div className="choice-copy"><div className="choice-heading"><h3>Valid payment</h3><StatusMark outcome="allowed" /></div><p>The recipient and amount match the approved plan.</p><span className="choice-expectation">Expected outcome</span></div></label>
              <label className={`scenario-choice ${selected === 'changed' ? 'is-selected' : ''}`}><input type="radio" name="example-scenario" value="changed" checked={selected === 'changed'} onChange={() => setSelected('changed')} /><div className="choice-copy"><div className="choice-heading"><h3>Recipient changed</h3><StatusMark outcome="blocked" /></div><p>The payment was redirected to someone else.</p><span className="choice-expectation">Expected outcome</span></div></label>
            </fieldset>
            <div className="control-examples"><div className="button-examples"><Button variant="secondary" onClick={resetPreview}><Icon name="reset" />Reset preview</Button><Button disabled aria-describedby="disabled-explanation">Run payment<Icon name="arrow" /></Button></div><p id="disabled-explanation">Payment runs are unavailable in this style preview.</p></div>
          </section>
          <aside className="review-note" aria-labelledby="review-title"><h2 id="review-title">Built for a clear demonstration.</h2><p>This is a visual foundation, using example content. The working demo will explain what was approved, what was sent, and whether the lock held.</p><p>Simulated governance. One trusted verifier. Checks cover defined actions and observed state.</p></aside>
        </main>
        <footer className="site-footer"><span>DAO Accountability Engine</span><span>Design foundations · Stage 1</span><a href="#main">Back to top ↑</a></footer>
      </div>
    </>
  )
}
