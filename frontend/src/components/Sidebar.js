import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { 
  Home, 
  Ticket, 
  Map, 
  Package, 
  LogOut, 
  User,
  Shield,
  Building2,
  Users,
  Layers,
  AlertTriangle
} from 'lucide-react';

const Sidebar = () => {
  const { user, logout } = useAuth();
  const location = useLocation();

  const allNavigation = [
    { name: 'Dashboard', href: '/dashboard', icon: Home, roles: ['admin', 'responder', 'viewer'] },
    { name: 'Tickets', href: '/tickets', icon: Ticket },
    { name: 'Map View', href: '/map', icon: Map },
    { name: 'Resources', href: '/resources', icon: Package },
    { name: 'Organizations', href: '/organizations', icon: Building2, roles: ['admin'] },
    { name: 'Staff', href: '/staff', icon: Users, roles: ['admin'] },
    { name: 'Divisions', href: '/divisions', icon: Layers, roles: ['admin'] },
    { name: 'Emergency Response', href: '/emergency-response', icon: AlertTriangle, roles: ['admin', 'responder'] },
  ];
  const role = user?.role || 'viewer';
  const navigation = allNavigation.filter((item) => !item.roles || item.roles.includes(role));

  const handleLogout = () => {
    logout();
  };

  return (
    <div className="w-64 bg-white shadow-lg border-r border-gray-200 flex flex-col">
      {/* Header */}
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg flex items-center justify-center">
            <Shield className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900">Disaster <br />Co-ordination Hub</h1>
            <p className="text-sm text-gray-500">Telangana</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 py-6 space-y-2">
        {navigation.map((item) => {
          const isActive = location.pathname === item.href;
          return (
            <NavLink
              key={item.name}
              to={item.href}
              className={`flex items-center space-x-3 px-4 py-3 rounded-lg transition-all duration-200 ${
                isActive
                  ? 'bg-blue-50 text-blue-700 border-r-2 border-blue-600'
                  : 'text-gray-700 hover:bg-gray-50 hover:text-gray-900'
              }`}
            >
              <item.icon className={`w-5 h-5 ${isActive ? 'text-blue-600' : 'text-gray-500'}`} />
              <span className="font-medium">{item.name}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* User Section */}
      <div className="p-4 border-t border-gray-200">
        <div className="flex items-center space-x-3 p-3 rounded-lg bg-gray-50">
          <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center">
            <User className="w-4 h-4 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900 truncate">
              {user?.username || 'User'}
            </p>
            <p className="text-xs text-gray-500 capitalize">
              {user?.role || 'viewer'}
            </p>
          </div>
        </div>
        
        <button
          onClick={handleLogout}
          className="w-full mt-3 flex items-center justify-center space-x-2 px-4 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors duration-200"
        >
          <LogOut className="w-4 h-4" />
          <span>Logout</span>
        </button>
      </div>

      {/* Status Indicator */}
      <div className="p-4 border-t border-gray-200">
        <div className="flex items-center space-x-2 text-xs text-gray-500">
          <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
          <span>System Online</span>
        </div>
      </div>
    </div>
  );
};

export default Sidebar;
