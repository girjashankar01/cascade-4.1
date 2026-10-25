import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import type { SectionId } from '../../data/types'
import { Icon } from '../ui/Icon'

const sections: { id: SectionId; label: string }[] = [
  { id: 'scenario', label: 'Scenario' }, { id: 'run', label: 'Run' }, { id: 'result', label: 'Result' }, { id: 'balances', label: 'Balances' }, { id: 'details', label: 'Details' },
]
export function SectionRail() {
  const location = useLocation()
  const pathname = location.pathname.replace(/\/+$/, '')
  const [expanded, setExpanded] = useState(false)
  const [active, setActive] = useState<SectionId>('scenario')
  const requested = useRef<SectionId | null>(null)
  const expectedScroll = useRef<number | null>(null)
  const arrived = useRef(false)
  const jumpTo = useCallback((id: SectionId) => {
    requested.current = id
    const target = document.getElementById(id)
    if (!target) return
    const margin = parseFloat(getComputedStyle(target).scrollMarginTop) || 0
    const padding = parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop) || 0
    expectedScroll.current = Math.max(0, Math.min(document.documentElement.scrollHeight - innerHeight, target.getBoundingClientRect().top + scrollY - margin - padding))
    arrived.current = Math.abs(scrollY - expectedScroll.current) <= 2
    target.scrollIntoView({ behavior: getComputedStyle(document.documentElement).scrollBehavior === 'smooth' ? 'smooth' : 'instant', block: 'start' })
  }, [])
  useEffect(() => {
    if (pathname !== '/app') return
    const targets = sections.map(section => document.getElementById(section.id)).filter((element): element is HTMLElement => Boolean(element))
    const updateVisible = () => {
      if (requested.current) { setActive(requested.current); return }
      if (scrollY + innerHeight >= document.documentElement.scrollHeight - 4) { setActive('details'); return }
      const visible = targets.filter(element => { const rect = element.getBoundingClientRect(); return rect.top < innerHeight * 0.45 && rect.bottom > 0 })
      if (visible.length) setActive(visible[visible.length - 1].id as SectionId)
    }
    const observer = new IntersectionObserver(updateVisible, { threshold: [0, 0.2, 0.5, 1] })
    const release = () => { requested.current = null; expectedScroll.current = null; arrived.current = false }
    const onScroll = () => {
      if (requested.current && expectedScroll.current !== null) {
        if (Math.abs(scrollY - expectedScroll.current) <= 2) arrived.current = true
        else if (arrived.current) release()
      }
      updateVisible()
    }
    const releaseOnPointer = (event: PointerEvent) => { if (!(event.target instanceof Element) || !event.target.closest('.section-navigation')) release() }
    const releaseOnKey = (event: KeyboardEvent) => { if (['ArrowDown', 'ArrowUp', 'PageDown', 'PageUp', 'Home', 'End', ' '].includes(event.key)) release() }
    window.addEventListener('wheel', release, { passive: true })
    window.addEventListener('touchmove', release, { passive: true })
    window.addEventListener('pointerdown', releaseOnPointer)
    window.addEventListener('keydown', releaseOnKey)
    window.addEventListener('scroll', onScroll, { passive: true })
    targets.forEach(element => observer.observe(element))
    return () => { observer.disconnect(); release(); window.removeEventListener('wheel', release); window.removeEventListener('touchmove', release); window.removeEventListener('pointerdown', releaseOnPointer); window.removeEventListener('keydown', releaseOnKey); window.removeEventListener('scroll', onScroll) }
  }, [pathname])
  useEffect(() => {
    const id = location.hash.slice(1)
    if (pathname === '/app' && sections.some(section => section.id === id)) {
      jumpTo(id as SectionId)
    }
  }, [pathname, location.hash, jumpTo])
  return <aside className={`section-rail ${expanded ? 'is-expanded' : ''}`}><nav aria-label="Sections in this workspace" className="section-navigation"><button className="rail-toggle" type="button" aria-label="Keep section labels visible" aria-pressed={expanded} onClick={() => setExpanded(value => !value)}><Icon name="menu" /><span>Sections</span></button>{sections.map(section => <Link key={section.id} to={{ pathname: '/app', search: location.search, hash: section.id }} onClick={() => { requested.current = section.id; setActive(section.id); if (pathname === '/app' && location.hash === `#${section.id}`) jumpTo(section.id) }} aria-label={section.label} aria-current={pathname === '/app' && active === section.id ? 'location' : undefined} className="rail-link"><Icon name={section.id} /><span>{section.label}</span></Link>)}</nav></aside>
}
