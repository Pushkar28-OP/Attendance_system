import { useEffect, useState } from 'react'
import { Check, MapPin, X } from 'lucide-react'
import api from './services/api'
import { formatKolkataDate, formatKolkataTime, kolkataDateKey } from './time'

function formatLocation(location) {
  if (!location || location.latitude == null || location.longitude == null) return 'Location unavailable'
  if (location.display_name) return location.display_name
  if (location.area) return location.city && !location.area.includes(location.city) ? `${location.area}, ${location.city}` : location.area
  return 'Area unavailable'
}

function accuracyLabel(accuracy) {
  if (accuracy == null) return 'Accuracy unavailable'
  if (accuracy <= 30) return `High accuracy (~${Math.round(accuracy)}m)`
  if (accuracy <= 100) return `Approximate location (~${Math.round(accuracy)}m)`
  return `Low accuracy (~${Math.round(accuracy)}m)`
}

function LocationDetails({ location }) {
  return <div className="location-details"><b>{formatLocation(location)}</b>{location?.accuracy != null && <small>{accuracyLabel(location.accuracy)}</small>}</div>
}

function detectDevice() {
  const userAgent = navigator.userAgent || ''
  if (/iPad|Tablet|Android/i.test(userAgent)) return 'Mobile / tablet'
  return 'Laptop / desktop'
}

function detectBrowser() {
  const userAgent = navigator.userAgent || ''
  if (/Edg\//i.test(userAgent)) return 'Edge'
  if (/Firefox\//i.test(userAgent)) return 'Firefox'
  if (/CriOS\//i.test(userAgent)) return 'Chrome on iOS'
  if (/Chrome\//i.test(userAgent)) return 'Chrome'
  if (/Safari\//i.test(userAgent) && !/Chrome\//i.test(userAgent)) return 'Safari'
  return 'Unknown browser'
}

function statusBadgeClass(status) {
  return status === 'ABSENT' ? 'badge absent' : 'badge verified'
}

function locationFailureMessage(error) {
  if (!window.isSecureContext) return 'Location requires localhost or HTTPS. Open the app on localhost/127.0.0.1 or serve it over HTTPS.'
  if (!navigator.geolocation) return 'This browser does not support location capture.'
  if (error?.code === 1) return 'Location permission was denied. Allow location access in the browser, then try again.'
  if (error?.code === 2) return 'The browser could not determine your location. Check device location services and try again.'
  if (error?.code === 3) return 'Location capture timed out. Try again, or move near a window for a better signal.'
  return 'Location unavailable.'
}

function requestFailureMessage(error) {
  const detail = error.response?.data?.detail
  if (Array.isArray(detail)) return detail.map(item => item.msg).join(' ')
  if (detail) return detail
  if (error.code === 'ERR_NETWORK') return 'Could not reach the attendance API. Confirm that the backend is running, then try again.'
  return error.message || 'Attendance could not be recorded.'
}

export default function LocationAttendance() {
  const [history, setHistory] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [locationDiagnostics, setLocationDiagnostics] = useState(null)
  const today = kolkataDateKey()
  const todayRecord = history.find(item => item.date === today)
  const action = todayRecord?.check_in_time && !todayRecord?.check_out_time ? 'check_out' : 'check_in'

  async function loadHistory() {
    const { data } = await api.get('/api/attendance/mine')
    setHistory(data)
    return data
  }

  useEffect(() => { loadHistory().catch(() => setError('Could not load attendance history.')) }, [])

  async function getLocationOnce(onStatus) {
    const diagnosticBase = { device: detectDevice(), browser: detectBrowser(), secureContext: window.isSecureContext, permission: 'unknown', readings: [], selected: null, watchDurationMs: 0 }
    let permission = 'unknown'
    try {
      permission = (await navigator.permissions?.query({ name: 'geolocation' }))?.state || 'unknown'
    } catch {
      permission = 'unknown'
    }
    diagnosticBase.permission = permission
    setLocationDiagnostics(diagnosticBase)
    if (!navigator.geolocation || !window.isSecureContext) {
      return { location: { latitude: null, longitude: null, accuracy: null, source: 'browser' }, warning: locationFailureMessage(), reason: 'unavailable' }
    }
    return new Promise(resolve => {
      const startedAt = Date.now()
      let bestPosition = null
      let watchId = null
      let timerId = null
      let settled = false
      const finish = (locationError = null) => {
        if (settled) return
        settled = true
        if (watchId != null) navigator.geolocation.clearWatch(watchId)
        if (timerId != null) window.clearTimeout(timerId)
        if (bestPosition) {
          const { latitude, longitude, accuracy } = bestPosition.coords
          const selected = { latitude, longitude, accuracy, altitude: bestPosition.coords.altitude, altitudeAccuracy: bestPosition.coords.altitudeAccuracy, heading: bestPosition.coords.heading, speed: bestPosition.coords.speed, timestamp: bestPosition.timestamp }
          setLocationDiagnostics(current => ({ ...current, selected, watchDurationMs: Date.now() - startedAt }))
          console.info('Attendance browser GeolocationPosition selected.', { source: 'browser geolocation (OS-selected provider)', position: bestPosition, ...selected })
          resolve({ location: { latitude, longitude, accuracy, source: 'browser' }, warning: '', reason: '' })
          return
        }
        console.warn('Attendance location capture failed.', { code: locationError?.code, message: locationError?.message })
        resolve({ location: { latitude: null, longitude: null, accuracy: null, source: 'browser' }, warning: locationFailureMessage(locationError), reason: locationError?.code === 1 ? 'permission-denied' : 'unavailable' })
      }
      const consider = position => {
        const reading = { latitude: position.coords.latitude, longitude: position.coords.longitude, accuracy: position.coords.accuracy, altitude: position.coords.altitude, altitudeAccuracy: position.coords.altitudeAccuracy, heading: position.coords.heading, speed: position.coords.speed, timestamp: position.timestamp }
        setLocationDiagnostics(current => ({ ...current, readings: [...(current?.readings || []), reading] }))
        console.info('Attendance browser GeolocationPosition reading.', { source: 'browser geolocation (OS-selected provider)', position, ...reading })
        if (!bestPosition || position.coords.accuracy < bestPosition.coords.accuracy) {
          bestPosition = position
          onStatus(`Location found. Accuracy approximately ${Math.round(position.coords.accuracy)}m. Improving fix...`)
          if (position.coords.accuracy <= 30) finish()
        }
      }
      const options = { enableHighAccuracy: true, timeout: 30000, maximumAge: 0 }
      navigator.geolocation.getCurrentPosition(consider, error => { if (error.code === 1 && !bestPosition) finish(error) }, options)
      watchId = navigator.geolocation.watchPosition(consider, error => { if (error.code === 1 && !bestPosition) finish(error) }, options)
      timerId = window.setTimeout(() => finish(), 15000)
    })
  }

  async function recordAttendance() {
    setBusy(true)
    setError('')
    setMessage('Getting your location...')
    try {
      const { location, warning, reason } = await getLocationOnce(status => setMessage(status))
      if (location.latitude === null || location.longitude === null) {
        setMessage(`${warning} Recording attendance without location.`)
      }
      const { data } = await api.post('/api/attendance/verify', { ...location, action })
      if (!data.success) throw new Error(data.message || 'Attendance could not be recorded.')
      const refreshedHistory = await loadHistory()
      const record = refreshedHistory.find(item => item.date === today)
      const savedLocation = action === 'check_in' ? record?.check_in_location : record?.check_out_location
      setLocationDiagnostics(current => current ? ({ ...current, resolvedArea: formatLocation(savedLocation) }) : current)
      const locationNote = location.latitude === null || location.longitude === null ? ` ${reason === 'permission-denied' ? 'Location unavailable — permission denied.' : 'Location unavailable.'}` : ` ${formatLocation(savedLocation)}. ${accuracyLabel(savedLocation?.accuracy)}`
      setMessage(`${action === 'check_in' ? 'Check-in' : 'Check-out'} recorded at ${formatKolkataTime(data.timestamp)} IST.${locationNote}`)
    } catch (requestError) {
      console.error('Attendance request failed.', { url: requestError.config?.url, status: requestError.response?.status, detail: requestError.response?.data?.detail, message: requestError.message })
      setError(requestFailureMessage(requestError))
      setMessage('')
    } finally {
      setBusy(false)
    }
  }

  async function undo(item, undoAction) {
    const label = undoAction === 'check_in' ? 'check-in' : 'check-out'
    if (!window.confirm(`Undo this ${label}?`)) return
    setError('')
    try {
      await api.delete(`/api/attendance/mine/${item.attendance_id}?action=${undoAction}`)
      setMessage(`${label[0].toUpperCase() + label.slice(1)} undone.`)
      await loadHistory()
    } catch (requestError) {
      setError(requestError.response?.data?.detail || `Could not undo ${label}.`)
    }
  }

  return <>
    <section className="hero-strip"><div><span className="eyebrow cyan">TODAY / {formatKolkataDate().toUpperCase()}</span><h2>Record your presence</h2><p>Tap once to record your attendance and current location when available.</p></div><div className="verification-state"><span className="pulse-dot"/> Attendance ready</div></section>
    <div className="attendance-grid"><section className="panel verification-panel"><div className="panel-heading"><div><span className="eyebrow">AURELIX ATTENDANCE</span><h3>{action === 'check_in' ? 'Check in' : 'Check out'}</h3></div><span className="step-count">LOCATION</span></div><button className="primary-button action-button" type="button" disabled={busy || (action === 'check_in' && todayRecord?.check_in_time) || (action === 'check_out' && todayRecord?.check_out_time)} onClick={recordAttendance}><MapPin size={18}/>{busy ? 'Getting location...' : action === 'check_in' ? 'Record check-in' : 'Record check-out'}</button>{message && <div className="success-box"><Check size={17}/>{message}</div>}{error && <div className="error-box"><X size={16}/>{error}</div>}<div className="checks"><span><MapPin size={15}/> One-time browser location</span><span><Check size={15}/> Server timestamp recorded</span></div>{import.meta.env.DEV && locationDiagnostics && <div className="location-diagnostics"><h4>Development location diagnostics</h4><span>Device: {locationDiagnostics.device}</span><span>Browser: {locationDiagnostics.browser}</span><span>Secure context: {locationDiagnostics.secureContext ? 'yes' : 'no'}</span><span>Permission: {locationDiagnostics.permission}</span><span>Readings: {locationDiagnostics.readings.length}</span>{locationDiagnostics.selected && <><span>Latitude: {locationDiagnostics.selected.latitude}</span><span>Longitude: {locationDiagnostics.selected.longitude}</span><span>Accuracy: {locationDiagnostics.selected.accuracy} meters</span><span>Timestamp: {new Date(locationDiagnostics.selected.timestamp).toISOString()}</span><span>Selected: lowest accuracy reading</span></>}{locationDiagnostics.resolvedArea && <span>Reverse-geocoded area: {locationDiagnostics.resolvedArea}</span>}</div>}</section><section className="panel status-panel"><div className="panel-heading"><h3>Today's status</h3></div><div className={todayRecord?.final_status === 'ABSENT' ? 'big-status absent' : 'big-status'}>{todayRecord?.final_status || 'READY'}<small>{todayRecord?.check_in_time ? `In ${formatKolkataTime(todayRecord.check_in_time)} IST` : 'No check-in recorded'}</small></div><div className="history-list">{todayRecord && <><div className="history-row"><span>Check-in location</span><LocationDetails location={todayRecord.check_in_location}/></div><div className="history-row"><span>Check-out</span><b>{todayRecord.check_out_time ? `${formatKolkataTime(todayRecord.check_out_time)} IST` : 'Open'}</b></div><div className="history-row"><span>Check-out location</span><LocationDetails location={todayRecord.check_out_location}/></div></>}</div></section></div>
    <section className="panel table-panel"><span className="eyebrow">MY ATTENDANCE</span><h2>Attendance history</h2><div className="history-list">{history.map(item => <div className="history-row attendance-history-row" key={item.attendance_id}><b>{item.date}</b><span>{item.check_in_time ? `${formatKolkataTime(item.check_in_time)} IST` : '-'}</span><LocationDetails location={item.check_in_location}/><span>{item.check_out_time ? `${formatKolkataTime(item.check_out_time)} IST` : 'Open'}</span><LocationDetails location={item.check_out_location}/><span className={statusBadgeClass(item.final_status)}>{item.final_status}</span>{item.check_in_time && <button className="ghost-button table-action" onClick={() => undo(item, 'check_in')}>Undo check-in</button>}{item.check_out_time && <button className="ghost-button table-action" onClick={() => undo(item, 'check_out')}>Undo check-out</button>}</div>)}</div></section>
  </>
}
