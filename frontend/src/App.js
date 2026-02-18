import React from 'react';
import { BrowserRouter as Router, Navigate, Route, Routes } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import Sidebar from './components/Sidebar';
import Home from './pages/Home';
import Dashboard from './pages/Dashboard';
import Tickets from './pages/Tickets';
import MapView from './pages/MapView';
import Resources from './pages/Resources';
import Organizations from './pages/Organizations';
import Staff from './pages/Staff';
import Divisions from './pages/Divisions';
import EmergencyResponse from './pages/EmergencyResponse';
import Login from './pages/Login';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import './index.css';

const ProtectedPage = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="spinner"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return children;
};

const RoleProtectedPage = ({ allowedRoles, children }) => {
  const { user } = useAuth();
  if (!user || !allowedRoles.includes(user.role)) {
    return <Navigate to="/dashboard" replace />;
  }
  return children;
};

const DashboardLayout = ({ children }) => (
  <div className="flex h-screen bg-gray-50">
    <Sidebar />
    <main className="flex-1 overflow-auto">{children}</main>
  </div>
);

function AppContent() {
  const { isAuthenticated } = useAuth();

  return (
    <>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <Login />} />

        <Route
          path="/dashboard"
          element={
            <ProtectedPage>
              <DashboardLayout>
                <Dashboard />
              </DashboardLayout>
            </ProtectedPage>
          }
        />
        <Route
          path="/tickets"
          element={
            <ProtectedPage>
              <DashboardLayout>
                <Tickets />
              </DashboardLayout>
            </ProtectedPage>
          }
        />
        <Route
          path="/map"
          element={
            <ProtectedPage>
              <DashboardLayout>
                <MapView />
              </DashboardLayout>
            </ProtectedPage>
          }
        />
        <Route
          path="/resources"
          element={
            <ProtectedPage>
              <DashboardLayout>
                <Resources />
              </DashboardLayout>
            </ProtectedPage>
          }
        />
        <Route
          path="/emergency-response"
          element={
            <ProtectedPage>
              <RoleProtectedPage allowedRoles={['admin', 'responder']}>
                <DashboardLayout>
                  <EmergencyResponse />
                </DashboardLayout>
              </RoleProtectedPage>
            </ProtectedPage>
          }
        />
        <Route
          path="/organizations"
          element={
            <ProtectedPage>
              <RoleProtectedPage allowedRoles={['admin']}>
                <DashboardLayout>
                  <Organizations />
                </DashboardLayout>
              </RoleProtectedPage>
            </ProtectedPage>
          }
        />
        <Route
          path="/staff"
          element={
            <ProtectedPage>
              <RoleProtectedPage allowedRoles={['admin']}>
                <DashboardLayout>
                  <Staff />
                </DashboardLayout>
              </RoleProtectedPage>
            </ProtectedPage>
          }
        />
        <Route
          path="/divisions"
          element={
            <ProtectedPage>
              <RoleProtectedPage allowedRoles={['admin']}>
                <DashboardLayout>
                  <Divisions />
                </DashboardLayout>
              </RoleProtectedPage>
            </ProtectedPage>
          }
        />

        <Route path="*" element={<Navigate to={isAuthenticated ? '/dashboard' : '/'} replace />} />
      </Routes>

      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: '#363636',
            color: '#fff',
          },
        }}
      />
    </>
  );
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <AppContent />
      </Router>
    </AuthProvider>
  );
}

export default App;

