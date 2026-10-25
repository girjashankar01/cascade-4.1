import { DataError } from './types.ts'
type ClientOptions = { baseUrl: string; fetcher?: typeof fetch; timeoutMs?: number }

export function createClient({ baseUrl, fetcher = fetch, timeoutMs }: ClientOptions) {
  let url: URL
  try { url = new URL(baseUrl) } catch { throw new DataError('CONFIGURATION', 'The local service address is not configured correctly. Use demo data.') }
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) throw new DataError('CONFIGURATION', 'The local service address is not configured correctly. Use demo data.')
  return async function request(path: string, method: 'GET' | 'POST' = 'GET', signal?: AbortSignal): Promise<unknown> {
    const timeout = AbortSignal.timeout(timeoutMs ?? (method === 'POST' ? 60000 : 10000))
    try {
      const response = await fetcher(`${baseUrl.replace(/\/$/, '')}${path}`, { method, signal: signal ? AbortSignal.any([signal, timeout]) : timeout, headers: { Accept: 'application/json', ...(method === 'POST' ? { 'Content-Type': 'application/json' } : {}) }, ...(method === 'POST' ? { body: '{}' } : {}) })
      if (!response.ok) throw new DataError('SERVICE_RESPONSE', method === 'POST' ? 'The live run did not return a confirmed result. Check the record before trying again.' : 'The local service could not provide this information. You can use demo data.')
      return await response.json()
    } catch (error) {
      if (signal?.aborted) throw new DataError('CANCELLED', 'The request was cancelled.')
      if (error instanceof DataError) throw error
      throw new DataError(method === 'POST' ? 'RUN_UNCONFIRMED' : 'UNREACHABLE', method === 'POST' ? 'The live run is not confirmed. Do not repeat it until its record has been checked.' : 'The local service is unavailable. You can keep using demo data.')
    }
  }
}
