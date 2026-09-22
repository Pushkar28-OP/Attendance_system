import { useEffect, useState } from 'react'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { ArrowLeft, ArrowRight, BarChart3, Check, ClipboardList, LogOut, MapPin, ShieldCheck, Trash2, UserPlus, Users, X } from 'lucide-react'
import api from './services/api'
import './adminEnhancements'
import LocationAttendance from './LocationAttendance'
import { formatKolkataTime, kolkataDateKey } from './time'

function formatLocation(location) {
  if (!location || location.latitude == null || location.longitude == null) return 'Unavailable'
  if (location.display_name) return location.display_name
  if (location.area) return location.city && !location.area.includes(location.city) ? `${location.area}, ${location.city}` : location.area
  return 'Location unavailable'
}

function statusBadgeClass(status) {
  return status === 'ABSENT' ? 'badge absent' : 'badge verified'
}

function Shell({ user, onLogout, children }) {
  const navigate = useNavigate()
  const location = useLocation()
  const isAdmin = user?.role === 'admin'
  const links = isAdmin ? [['/admin', BarChart3, 'Command center'], ['/admin/employees', Users, 'People']] : [['/attendance', MapPin, 'Attendance'], ['/history', ClipboardList, 'My history']]
  return <div className="app-shell"><aside className="sidebar"><div className="brand"><img className="brand-logo" src="/aurelix-logo.png" alt="" onError={event => { event.currentTarget.style.display = 'none' }} /><span className="brand-fallback">AURELIX<small>SMART ATTENDANCE</small></span></div><div className="workspace-label">Workspace / {isAdmin ? 'Operations' : 'Employee'}</div><nav>{links.map(([path, Icon, label]) => <button className={location.pathname === path ? 'nav-item active' : 'nav-item'} onClick={() => navigate(path)} key={path}><Icon size={17}/>{label}</button>)}</nav><div className="sidebar-bottom"><div className="user-chip"><span className="avatar">{user.full_name?.slice(0, 1)}</span><span><b>{user.full_name}</b><small>{user.department}</small></span></div><button className="nav-item" onClick={onLogout}><LogOut size={17}/>Sign out</button></div></aside><main className="main-content"><header className="topbar"><div><span className="eyebrow">AURELIX / {isAdmin ? 'OPERATIONS' : 'PERSONAL SPACE'}</span><h1>{isAdmin ? 'Attendance command center' : 'Good to see you, ' + user.full_name.split(' ')[0]}</h1></div><span className="secure-pill"><ShieldCheck size={14}/> Secure session</span></header>{children}</main></div>
}

function Login({ onLogin }) {
  const [form, setForm] = useState({ email: '', password: '' })
  const [error, setError] = useState('')
  const navigate = useNavigate()
  async function submit(event) {
    event.preventDefault()
    setError('')
    try {
      const { data } = await api.post('/api/auth/login', form)
      localStorage.setItem('aurelix_token', data.access_token)
      onLogin(data.user)
      navigate(data.user.role === 'admin' ? '/admin' : '/attendance')
    } catch (err) {
      setError(err.response?.data?.detail || 'Unable to sign in right now.')
    }
  }
  return <div className="login-page"><div className="login-visual"><div className="brand"><span className="brand-mark">A</span><span>AURELIX<small>SMART ATTENDANCE</small></span></div><div className="visual-copy"><span className="eyebrow cyan">ATTENDANCE / TIME / PLACE</span><h1>Presence, recorded.</h1><p>Check in and check out with a secure account, server time, and a one-time location capture.</p></div><div className="signal-grid"><span><b>01</b> SECURE LOGIN</span><span><b>02</b> SERVER TIME</span><span><b>03</b> LOCATION STORED</span></div></div><form className="login-card" onSubmit={submit}><span className="eyebrow">WELCOME BACK</span><h2>Sign in to your workspace</h2><p className="muted">Use your Aurelix credentials to continue.</p><label>Work email<input type="email" required value={form.email} onChange={event => setForm({ ...form, email: event.target.value })} placeholder="you@aurelix.com" /></label><label>Password<input type="password" required value={form.password} onChange={event => setForm({ ...form, password: event.target.value })} placeholder="Password" /></label>{error && <div className="error-box"><X size={16}/>{error}</div>}<button className="primary-button" type="submit">Enter workspace <ArrowRight size={17}/></button><small className="form-note">Protected by JWT authentication and role-based access.</small></form></div>
}

function AdminDashboard() {
  async function clearRecord(attendanceId) {
    if (!window.confirm('Clear this attendance record?')) return
    await api.delete(`/api/attendance/admin/${attendanceId}`)
    window.location.reload()
  }
  const today = kolkataDateKey()
  const [selectedDate, setSelectedDate] = useState(today)
  const [month, setMonth] = useState(today.slice(0, 7))
  const [stats, setStats] = useState({})
  const [records, setRecords] = useState([])
  const [monthRecords, setMonthRecords] = useState([])
  useEffect(() => { api.get(`/api/attendance/admin?date=${selectedDate}`).then(({ data }) => { setRecords(data); const present = data.filter(item => item.final_status === 'PRESENT').length; setStats({ total_employees: data.length, present_today: present, absent_today: data.length - present }) }).catch(() => {}) }, [selectedDate])
  useEffect(() => { api.get(`/api/attendance/admin/month?month=${month}`).then(({ data }) => setMonthRecords(data)).catch(() => {}) }, [month])
  function chooseDate(value) { if (value) { setSelectedDate(value); setMonth(value.slice(0, 7)) } }
  function shiftMonth(amount) {
    const [year, monthNumber] = month.split('-').map(Number)
    const nextDate = new Date(year, monthNumber - 1 + amount, 1)
    const next = `${nextDate.getFullYear()}-${String(nextDate.getMonth() + 1).padStart(2, '0')}`
    setMonth(next)
    setSelectedDate(`${next}-01`)
  }
  function renderCalendar() {
    const [year, monthNumber] = month.split('-').map(Number)
    const days = new Date(year, monthNumber, 0).getDate()
    const offset = new Date(year, monthNumber - 1, 1).getDay()
    const summaries = monthRecords.reduce((result, item) => ({ ...result, [item.date]: (result[item.date] || 0) + (item.final_status === 'PRESENT' ? 1 : 0) }), {})
    return [...Array(offset).fill(null).map((_, index) => <span className="calendar-day empty" key={`empty-${index}`} />), ...Array.from({ length: days }, (_, index) => { const date = `${month}-${String(index + 1).padStart(2, '0')}`; return <button type="button" className={date === selectedDate ? 'calendar-day selected' : 'calendar-day'} onClick={() => chooseDate(date)} key={date}><b>{index + 1}</b>{summaries[date] ? <small>{summaries[date]} present</small> : <small>-</small>}</button> })]
  }
  async function exportData() {
    const response = await api.get(`/api/admin/export?date=${selectedDate}`, { responseType: 'blob' })
    const url = URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = url
    link.download = `aurelix-attendance-${selectedDate}.xlsx`
    link.click()
    URL.revokeObjectURL(url)
  }
  return <><section className="hero-strip compact"><div><span className="eyebrow cyan">LIVE OPERATIONS / OVERVIEW</span><h2>Attendance register</h2><p>Review employee attendance by day and export the stored check-in/check-out records.</p></div><label className="date-picker">Selected day<input type="date" value={selectedDate} onChange={event => chooseDate(event.target.value)} /></label></section><div className="stats-grid">{[['TOTAL EMPLOYEES', stats.total_employees, Users], ['PRESENT', stats.present_today, Check], ['ABSENT', stats.absent_today, X]].map(([label, value, Icon]) => <div className="stat-card" key={label}><Icon size={17}/><span>{label}</span><strong>{value ?? '-'}</strong></div>)}</div><div className="admin-dashboard-grid"><section className="panel calendar-panel"><div className="panel-heading"><div><span className="eyebrow">ATTENDANCE CALENDAR</span><h3>{new Date(Number(month.slice(0, 4)), Number(month.slice(5, 7)) - 1, 1).toLocaleDateString(undefined, { month: 'long', year: 'numeric' })}</h3></div><div className="calendar-actions"><button className="icon-button" title="Previous month" onClick={() => shiftMonth(-1)}><ArrowLeft size={16}/></button><button className="icon-button" title="Next month" onClick={() => shiftMonth(1)}><ArrowRight size={16}/></button></div></div><div className="calendar-weekdays">{['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(day => <span key={day}>{day}</span>)}</div><div className="calendar-grid">{renderCalendar()}</div></section><section className="panel table-panel"><div className="panel-heading"><div><span className="eyebrow">ATTENDANCE LOG / {selectedDate}</span><h3>Daily Attendance Register</h3></div><button className="ghost-button" onClick={exportData}>Export data</button></div><div className="table-scroll"><table><thead><tr><th>Employee</th><th>Department</th><th>In</th><th>In location</th><th>Out</th><th>Out location</th><th>Status</th><th>Action</th></tr></thead><tbody>{records.map(item => <tr key={item.attendance_id}><td><b>{item.employee?.full_name || item.user_name || item.employee_id}</b><small>{item.employee_id}</small></td><td>{item.employee?.department || '-'}</td><td>{item.check_in_time ? `${formatKolkataTime(item.check_in_time)} IST` : '-'}</td><td>{formatLocation(item.check_in_location)}</td><td>{item.check_out_time ? `${formatKolkataTime(item.check_out_time)} IST` : 'Open'}</td><td>{formatLocation(item.check_out_location)}</td><td><span className={item.final_status === 'PRESENT' ? 'badge verified' : 'badge absent'}>{item.final_status}</span></td><td><button className="ghost-button table-action" onClick={() => clearRecord(item.attendance_id)} disabled={item.attendance_id.startsWith('absent-')}>Undo record</button></td></tr>)}</tbody></table>{!records.length && <div className="empty-state">No active employees found.</div>}</div></section></div></>
}

function CreateEmployeePanel({ onCreated }) {
  const [form, setForm] = useState({ employee_id: '', full_name: '', email: '', department: '', role: 'employee', password: '' })
  const [message, setMessage] = useState('')
  async function submit(event) {
    event.preventDefault()
    try {
      await api.post('/api/employees', form)
      setMessage('Employee created successfully.')
      setForm({ employee_id: '', full_name: '', email: '', department: '', role: 'employee', password: '' })
      onCreated()
    } catch (error) {
      const detail = error.response?.data?.detail
      setMessage(Array.isArray(detail) ? detail.map(item => item.msg).join(' ') : detail || 'Could not create employee.')
    }
  }
  return <section className="panel form-panel"><span className="eyebrow">PEOPLE / NEW RECORD</span><h2>Add employee</h2><form className="employee-form" onSubmit={submit}>{[['employee_id','Employee ID'],['full_name','Full name'],['email','Work email'],['department','Department'],['password','Temporary password']].map(([key, label]) => <label key={key}>{label}<input required={key !== 'password'} type={key === 'email' ? 'email' : key === 'password' ? 'password' : 'text'} value={form[key]} onChange={event => setForm({ ...form, [key]: event.target.value })}/></label>)}<button className="primary-button" type="submit"><UserPlus size={17}/> Add employee</button></form>{message && <div className={message.startsWith('Employee created') ? 'success-box' : 'error-box'}><Check size={17}/>{message}</div>}</section>
}

function EmployeeEditor() {
  const [employees, setEmployees] = useState([])
  const [selectedId, setSelectedId] = useState('')
  const [form, setForm] = useState(null)
  const [message, setMessage] = useState('')
  async function load() {
    const { data } = await api.get('/api/employees')
    setEmployees(data)
    if (selectedId) {
      const selected = data.find(item => item.employee_id === selectedId)
      if (selected) setForm(current => current || { ...selected, password: '' })
    }
  }
  useEffect(() => { load().catch(() => {}) }, [])
  function selectEmployee(id) {
    const selected = employees.find(item => item.employee_id === id)
    setSelectedId(id)
    setForm(selected ? { ...selected, password: '' } : null)
    setMessage('')
  }
  async function save(event) {
    event.preventDefault()
    try {
      await api.put(`/api/employees/${selectedId}`, { employee_id: form.employee_id, full_name: form.full_name, email: form.email, department: form.department, role: form.role, password: form.password || null })
      setMessage('Employee details saved successfully.')
      await load()
    } catch (error) {
      const detail = error.response?.data?.detail
      setMessage(Array.isArray(detail) ? detail.map(item => item.msg).join(' ') : detail || 'Could not save employee details.')
    }
  }
  async function remove() {
    if (!form || !window.confirm(`Remove ${form.full_name}? Attendance history will be kept.`)) return
    try {
      await api.delete(`/api/employees/${selectedId}`)
      setMessage('Employee removed.')
      setSelectedId('')
      setForm(null)
      await load()
    } catch (error) {
      setMessage(error.response?.data?.detail || 'Could not remove employee.')
    }
  }
  return <div className="admin-people-grid"><CreateEmployeePanel onCreated={load}/><section className="panel"><span className="eyebrow">PEOPLE / DIRECTORY</span><h2>Members and admins</h2><div className="people-list">{employees.map(item => <button type="button" className={item.employee_id === selectedId ? 'person-row selected-person' : 'person-row'} onClick={() => selectEmployee(item.employee_id)} key={item.employee_id}><span><b>{item.full_name}</b><small>{item.employee_id} - {item.department} - {item.role}</small></span><span className="muted">Edit</span></button>)}</div></section><section className="panel">{form ? <><span className="eyebrow">PEOPLE / EDIT RECORD</span><h2>Edit employee details</h2><form className="employee-form" onSubmit={save}>{[['employee_id','Employee ID'],['full_name','Full name'],['email','Work email'],['department','Department'],['password','New password']].map(([key, label]) => <label key={key}>{label}<input type={key === 'email' ? 'email' : key === 'password' ? 'password' : 'text'} value={form[key] || ''} onChange={event => setForm({ ...form, [key]: event.target.value })}/></label>)}<button className="primary-button" type="submit">Save changes</button><button className="ghost-button" type="button" onClick={remove}><Trash2 size={16}/> Remove employee</button></form>{message && <div className="success-box"><Check size={17}/>{message}</div>}</> : <><span className="eyebrow">PEOPLE / EDIT RECORD</span><h2>Select a person</h2><p className="muted">Choose a person from the directory to edit their details.</p></>}</section></div>
}

function History() {
  const [items, setItems] = useState([])
  const [error, setError] = useState('')
  async function load() { const { data } = await api.get('/api/attendance/mine'); setItems(data) }
  useEffect(() => { load().catch(() => setError('Could not load attendance history.')) }, [])
  async function undo(item, action) {
    const label = action === 'check_in' ? 'check-in time' : 'check-out time'
    if (!window.confirm(`Undo this ${label}?`)) return
    setError('')
    try {
      await api.delete(`/api/attendance/mine/${item.attendance_id}?action=${action}`)
      await load()
    } catch (err) {
      setError(err.response?.data?.detail || `Could not undo ${label}.`)
    }
  }
  return <section className="panel table-panel"><span className="eyebrow">MY ATTENDANCE</span><h2>Attendance history</h2>{error && <div className="error-box"><X size={16}/>{error}</div>}<div className="table-scroll"><table><thead><tr><th>Date</th><th>Check in</th><th>Check-in location</th><th>Check out</th><th>Check-out location</th><th>Status</th><th>Actions</th></tr></thead><tbody>{items.map(item => <tr key={item.attendance_id}><td><b>{item.date}</b></td><td>{item.check_in_time ? `${formatKolkataTime(item.check_in_time)} IST` : '-'}</td><td>{formatLocation(item.check_in_location)}</td><td>{item.check_out_time ? `${formatKolkataTime(item.check_out_time)} IST` : 'Open'}</td><td>{formatLocation(item.check_out_location)}</td><td><span className={statusBadgeClass(item.final_status)}>{item.final_status}</span></td><td><button className="ghost-button table-action" disabled={!item.check_in_time} onClick={() => undo(item, 'check_in')}>Undo check-in</button><button className="ghost-button table-action" disabled={!item.check_out_time} onClick={() => undo(item, 'check_out')}>Undo check-out</button></td></tr>)}</tbody></table></div></section>
}

export default function App() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  useEffect(() => { if (localStorage.getItem('aurelix_token')) api.get('/api/auth/me').then(({ data }) => setUser(data)).catch(() => localStorage.removeItem('aurelix_token')).finally(() => setLoading(false)); else setLoading(false) }, [])
  if (loading) return <div className="loading">Loading secure workspace...</div>
  if (!user) return <Routes><Route path="*" element={<Login onLogin={setUser}/>}/></Routes>
  const logout = () => { localStorage.removeItem('aurelix_token'); setUser(null) }
  return <Shell user={user} onLogout={logout}><Routes><Route path="/" element={<Navigate to={user.role === 'admin' ? '/admin' : '/attendance'} replace/>}/><Route path="/attendance" element={<LocationAttendance/>}/><Route path="/history" element={<History/>}/><Route path="/admin" element={user.role === 'admin' ? <AdminDashboard/> : <Navigate to="/attendance"/>}/><Route path="/admin/employees" element={user.role === 'admin' ? <EmployeeEditor/> : <Navigate to="/attendance"/>}/><Route path="*" element={<Navigate to="/" replace/>}/></Routes></Shell>
}
