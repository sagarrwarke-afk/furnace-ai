import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import UploadPage from './pages/UploadPage'
import FleetOverview from './pages/FleetOverview'
import FeedPlanning from './pages/FeedPlanning'
import FurnaceDetail from './pages/FurnaceDetail'
import WhatIfSimulator from './pages/WhatIfSimulator'
import SensitivityManager from './pages/SensitivityManager'
import SettingsPage from './pages/SettingsPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Navigate to="/fleet" replace />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/fleet" element={<FleetOverview />} />
          <Route path="/planning" element={<FeedPlanning />} />
          <Route path="/furnace" element={<FurnaceDetail />} />
          <Route path="/whatif" element={<WhatIfSimulator />} />
          <Route path="/sensitivity" element={<SensitivityManager />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
