const KOLKATA_TIME_ZONE = 'Asia/Kolkata'

export function kolkataDateKey(date = new Date()) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: KOLKATA_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date)
  const values = Object.fromEntries(parts.map(part => [part.type, part.value]))
  return `${values.year}-${values.month}-${values.day}`
}

export function formatKolkataTime(value) {
  return new Intl.DateTimeFormat('en-IN', {
    timeZone: KOLKATA_TIME_ZONE,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  }).format(new Date(value))
}

export function formatKolkataDate(value = new Date()) {
  return new Intl.DateTimeFormat('en-IN', {
    timeZone: KOLKATA_TIME_ZONE,
    weekday: 'long',
    month: 'short',
    day: 'numeric',
  }).format(new Date(value))
}
