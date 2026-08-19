import axios from 'axios'

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000' })
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('aurelix_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
api.interceptors.response.use((response) => {
  if (response.data?.location_diagnostics) {
    window.dispatchEvent(new CustomEvent('aurelix:location-diagnostics', { detail: response.data.location_diagnostics }))
  }
  return response
})
export default api
