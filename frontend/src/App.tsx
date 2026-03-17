import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import UploadPage from './pages/UploadPage'
import FleetOverview from './pages/FleetOverview'
import FeedPlanning from './pages/FeedPlanning'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Navigate to="/fleet" replace />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/fleet" element={<FleetOverview />} />
          <Route path="/planning" element={<FeedPlanning />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
