import { useEffect, useState } from 'react'
import { getDataService } from '../data/api'
import { DataError } from '../data/types'
import type { Connection, Mode } from '../data/types'

export function useConnection(mode: Mode, workspaceId: string) {
  const [attempt, setAttempt] = useState(0)
  const key = `${workspaceId}:${mode}:${attempt}`
  const [state, setState] = useState<{ key: string; value: Connection; diagnostic: string } | null>(null)
  useEffect(() => {
    const abort = new AbortController()
    getDataService().connection(mode, abort.signal).then(connection => { if (!abort.signal.aborted) setState({ key, value: connection, diagnostic: '' }) }).catch(error => {
      if (!abort.signal.aborted) {
        setState({ key, value: { service: 'offline', chain: 'offline', message: 'The local service is unavailable. You can keep using demo data.' }, diagnostic: error instanceof DataError ? error.code : 'SERVICE_UNAVAILABLE' })
      }
    })
    return () => abort.abort()
  }, [mode, key])
  return { connection: state?.key === key ? state.value : null, checking: state?.key !== key, diagnostic: state?.key === key ? state.diagnostic : '', retry: () => setAttempt(value => value + 1) }
}
