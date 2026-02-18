import React, { useState, useEffect } from 'react';
import { 
  Users, 
  AlertTriangle, 
  CheckCircle, 
  MapPin,
  Activity,
  Building2,
  Layers
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import axios from 'axios';
import toast from 'react-hot-toast';
import { useAuth } from '../contexts/AuthContext';

const Dashboard = () => {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [regionStats, setRegionStats] = useState([]);
  const [recentActivity, setRecentActivity] = useState([]);
  const [criticalAlerts, setCriticalAlerts] = useState(null);
  const [orgStats, setOrgStats] = useState(null);
  const [staffStats, setStaffStats] = useState(null);
  const [divisionStats, setDivisionStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      const [statsRes, regionRes, activityRes, alertsRes, orgRes, staffRes, divisionRes] = await Promise.all([
        axios.get('/api/dashboard/stats'),
        axios.get('/api/dashboard/regions'),
        axios.get('/api/dashboard/recent-activity'),
        axios.get('/api/dashboard/critical-alerts'),
        axios.get('/api/organizations/overview/stats'),
        axios.get('/api/staff/overview/stats'),
        axios.get('/api/divisions/overview/stats')
      ]);

      setStats(statsRes.data);
      setRegionStats(regionRes.data);
      setRecentActivity(activityRes.data);
      setCriticalAlerts(alertsRes.data);
      setOrgStats(orgRes.data);
      setStaffStats(staffRes.data);
      setDivisionStats(divisionRes.data);
    } catch (error) {
      toast.error('Failed to fetch dashboard data');
      console.error('Dashboard data fetch error:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="spinner"></div>
      </div>
    );
  }

  const chartData = regionStats.map(region => ({
    name: region.region,
    'SOS Requests': region.sos_count,
    'People Affected': region.people_affected
  }));

  const pieData = [
    { name: 'Pending', value: stats?.pending_sos || 0, color: '#f59e0b' },
    { name: 'In Progress', value: stats?.in_progress_sos || 0, color: '#3b82f6' },
    { name: 'Completed', value: stats?.completed_sos || 0, color: '#22c55e' }
  ];

  const orgTypeData = orgStats?.type_breakdown?.map(item => ({
    name: item.type,
    value: item.count,
    color: item.type === 'Government' ? '#8b5cf6' : 
           item.type === 'NGO' ? '#f97316' : 
           item.type === 'Volunteer Group' ? '#ec4899' : '#6366f1'
  })) || [];

  const staffRoleData = staffStats?.role_breakdown?.map(item => ({
    name: item.role,
    value: item.count,
    color: item.role === 'Manager' ? '#8b5cf6' : 
           item.role === 'Specialist' ? '#3b82f6' : 
           item.role === 'Worker' ? '#f97316' : '#ec4899'
  })) || [];

  const roleCapabilities = {
    admin: 'Full control over tickets, emergency operations, organizations, staff, divisions and resources.',
    responder: 'Can manage incidents and emergency response workflows with operational updates.',
    viewer: 'Read-only monitoring access to dashboards, maps and incident visibility.',
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-600">Overview of disaster response operations</p>
          <p className="text-sm text-blue-700 mt-1">
            Role: <span className="font-semibold capitalize">{user?.role || 'viewer'}</span> - {roleCapabilities[user?.role] || roleCapabilities.viewer}
          </p>
        </div>
        <div className="flex items-center space-x-2 text-sm text-gray-500">
          <Activity className="w-4 h-4" />
          <span>Last updated: {new Date().toLocaleTimeString()}</span>
        </div>
      </div>

      {/* Main Statistics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* SOS Requests */}
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Total SOS Requests</p>
              <p className="text-2xl font-bold text-gray-900">{stats?.total_sos || 0}</p>
            </div>
            <AlertTriangle className="w-8 h-8 text-red-600" />
          </div>
          <div className="mt-4 flex items-center text-sm">
            <span className="text-gray-500">Pending: </span>
            <span className="ml-1 font-medium text-yellow-600">{stats?.pending_sos || 0}</span>
            <span className="text-gray-500 ml-4">In Progress: </span>
            <span className="ml-1 font-medium text-blue-600">{stats?.in_progress_sos || 0}</span>
          </div>
        </div>

        {/* People Affected */}
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">People Affected</p>
              <p className="text-2xl font-bold text-gray-900">{stats?.total_people_affected || 0}</p>
            </div>
            <Users className="w-8 h-8 text-blue-600" />
          </div>
          <div className="mt-4 flex items-center text-sm">
            <span className="text-gray-500">Active Cases: </span>
            <span className="ml-1 font-medium text-orange-600">
              {(stats?.pending_sos || 0) + (stats?.in_progress_sos || 0)}
            </span>
          </div>
        </div>

        {/* Organizations */}
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Organizations</p>
              <p className="text-2xl font-bold text-gray-900">{orgStats?.total_organizations || 0}</p>
            </div>
            <Building2 className="w-8 h-8 text-purple-600" />
          </div>
          <div className="mt-4 flex items-center text-sm">
            <span className="text-gray-500">Capacity: </span>
            <span className="ml-1 font-medium text-green-600">{orgStats?.total_capacity || 0}</span>
            <span className="text-gray-500 ml-4">Load: </span>
            <span className="ml-1 font-medium text-orange-600">{orgStats?.current_load || 0}</span>
          </div>
        </div>

        {/* Staff */}
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Staff Members</p>
              <p className="text-2xl font-bold text-gray-900">{staffStats?.total_staff || 0}</p>
            </div>
            <Users className="w-8 h-8 text-green-600" />
          </div>
          <div className="mt-4 flex items-center text-sm">
            <span className="text-gray-500">Available: </span>
            <span className="ml-1 font-medium text-green-600">{staffStats?.available_staff || 0}</span>
            <span className="text-gray-500 ml-4">Active: </span>
            <span className="ml-1 font-medium text-blue-600">{staffStats?.active_staff || 0}</span>
          </div>
        </div>
      </div>

      {/* Secondary Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Shelters */}
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Shelters</h3>
            <MapPin className="w-6 h-6 text-green-600" />
          </div>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-gray-600">Total Capacity:</span>
              <span className="font-medium">{stats?.total_shelter_capacity || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Available:</span>
              <span className="font-medium text-green-600">{stats?.available_shelter_capacity || 0}</span>
            </div>
          </div>
        </div>

        {/* Hospitals */}
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Hospitals</h3>
            <Activity className="w-6 h-6 text-blue-600" />
          </div>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-gray-600">Total Beds:</span>
              <span className="font-medium">{stats?.total_hospital_beds || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Available:</span>
              <span className="font-medium text-green-600">{stats?.available_hospital_beds || 0}</span>
            </div>
          </div>
        </div>

        {/* Divisions */}
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Divisions</h3>
            <Layers className="w-6 h-6 text-purple-600" />
          </div>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-gray-600">Total:</span>
              <span className="font-medium">{divisionStats?.total_divisions || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Active:</span>
              <span className="font-medium text-green-600">{divisionStats?.active_divisions || 0}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* SOS Requests by Region */}
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">SOS Requests by Region</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="SOS Requests" fill="#3b82f6" />
              <Bar dataKey="People Affected" fill="#ef4444" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* SOS Status Distribution */}
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">SOS Status Distribution</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {pieData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Organization and Staff Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Organization Types */}
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Organization Types</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={orgTypeData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {orgTypeData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Staff Roles */}
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Staff Roles</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={staffRoleData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {staffRoleData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Recent Activity and Critical Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Activity */}
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Recent Activity</h3>
          <div className="space-y-4">
            {recentActivity.slice(0, 5).map((activity, index) => (
              <div key={index} className="flex items-start space-x-3">
                <div className="w-2 h-2 bg-blue-500 rounded-full mt-2"></div>
                <div className="flex-1">
                  <p className="text-sm text-gray-900">{activity.description}</p>
                  <p className="text-xs text-gray-500">{new Date(activity.timestamp).toLocaleString()}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Critical Alerts */}
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Critical Alerts</h3>
          {criticalAlerts && criticalAlerts.length > 0 ? (
            <div className="space-y-4">
              {criticalAlerts.slice(0, 5).map((alert, index) => (
                <div key={index} className="flex items-start space-x-3 p-3 bg-red-50 rounded-lg">
                  <AlertTriangle className="w-5 h-5 text-red-600 mt-0.5" />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-red-900">{alert.title}</p>
                    <p className="text-xs text-red-700">{alert.description}</p>
                    <p className="text-xs text-red-600 mt-1">{new Date(alert.timestamp).toLocaleString()}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-2" />
              <p className="text-gray-500">No critical alerts at the moment</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
