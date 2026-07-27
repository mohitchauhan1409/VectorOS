import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from '@/lib/auth'
import { PipelineProvider } from '@/lib/pipeline'
import { Sidebar } from '@/components/shell/Sidebar'
import { TopBar } from '@/components/shell/TopBar'
import { LoginPage } from '@/pages/LoginPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { AnalyticsPage } from '@/pages/AnalyticsPage'
import { PeoplePage } from '@/pages/PeoplePage'
import { CompaniesPage } from '@/pages/CompaniesPage'
import { CampaignsPage } from '@/pages/CampaignsPage'
import { PlaceholderPage } from '@/pages/PlaceholderPage'
import { Spinner } from '@/components/ui/Misc'

function Shell() {
  return (
    <PipelineProvider>
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <TopBar />
          <main className="flex-1 overflow-y-auto bg-canvas">
            <div className="mx-auto max-w-content px-8 py-6">
              <Routes>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/analytics" element={<AnalyticsPage />} />
                <Route path="/people" element={<PeoplePage />} />
                <Route path="/companies" element={<CompaniesPage />} />
                <Route path="/campaigns" element={<CampaignsPage />} />
                <Route
                  path="/lists"
                  element={<PlaceholderPage title="Lists" subtitle="Saved segments of people and companies." />}
                />
                <Route
                  path="/inbox"
                  element={<PlaceholderPage title="Inbox" subtitle="Unified reply inbox across email and LinkedIn." />}
                />
                <Route
                  path="/signals"
                  element={<PlaceholderPage title="Signals" subtitle="Live buying-signal feed from Scout." />}
                />
                <Route
                  path="/settings"
                  element={<PlaceholderPage title="Settings" subtitle="Workspace, mailboxes, and integrations." />}
                />
                <Route
                  path="/help"
                  element={<PlaceholderPage title="Help & docs" subtitle="Guides and keyboard shortcuts." />}
                />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </div>
          </main>
        </div>
      </div>
    </PipelineProvider>
  )
}

function Root() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-canvas text-gray-400">
        <Spinner size={24} />
      </div>
    )
  }

  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    )
  }

  return <Shell />
}

export default function App() {
  return (
    <AuthProvider>
      <Root />
    </AuthProvider>
  )
}
