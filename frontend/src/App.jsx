import React from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import Layout from './components/Layout';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import LabsAndRubricsPage from './pages/LabsAndRubricsPage';
import PortfolioPage from './pages/PortfolioPage';
import EvaluationDetailPage from './pages/EvaluationDetailPage';
import IntegratedReportPage from './pages/IntegratedReportPage';
import MindMapPage from './pages/MindMapPage';
import SettingsPage from './pages/SettingsPage';
import AboutTeamPage from './pages/AboutTeamPage';

function PrivateRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-sm text-slate-500">
        Verificando sesión...
      </div>
    );
  }
  return user ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <PrivateRoute>
            <Layout />
          </PrivateRoute>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="labs" element={<LabsAndRubricsPage />} />
        <Route path="portfolio" element={<PortfolioPage />} />
        <Route path="evaluations/:id" element={<EvaluationDetailPage />} />
        <Route path="report" element={<IntegratedReportPage />} />
        <Route path="mindmap" element={<MindMapPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="about" element={<AboutTeamPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
