import React, { useState, useEffect } from 'react';
import { 
  Activity, 
  Users, 
  Plus, 
  Edit, 
  Trash2, 
  Search,
  TrendingUp,
  CheckCircle,
  Building2
} from 'lucide-react';
import axios from 'axios';
import toast from 'react-hot-toast';

const emptyDivisionForm = {
  name: '',
  organization_id: '',
  type: 'Rescue',
  description: '',
  capacity: 100,
  current_load: 0,
  status: 'Active'
};

const Divisions = () => {
  const [divisions, setDivisions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [filters, setFilters] = useState({
    organization_id: '',
    type: '',
    status: ''
  });
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingDivision, setEditingDivision] = useState(null);
  const [stats, setStats] = useState(null);
  const [organizations, setOrganizations] = useState([]);
  const [formData, setFormData] = useState(emptyDivisionForm);

  useEffect(() => {
    fetchDivisions();
    fetchStats();
    fetchOrganizations();
  }, []);

  const fetchDivisions = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/divisions/');
      setDivisions(response.data);
    } catch (error) {
      toast.error('Failed to fetch divisions');
      console.error('Error fetching divisions:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await axios.get('/api/divisions/overview/stats');
      setStats(response.data);
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  };

  const fetchOrganizations = async () => {
    try {
      const response = await axios.get('/api/organizations/');
      setOrganizations(response.data);
    } catch (error) {
      console.error('Error fetching organizations:', error);
    }
  };

  const openCreateModal = () => {
    setEditingDivision(null);
    setFormData(emptyDivisionForm);
    setShowCreateModal(true);
  };

  const openEditModal = (division) => {
    setEditingDivision(division);
    setFormData({
      name: division.name || '',
      organization_id: division.organization_id || '',
      type: division.type || 'Rescue',
      description: division.description || '',
      capacity: division.capacity || 0,
      current_load: division.current_load || 0,
      status: division.status || 'Active'
    });
    setShowCreateModal(true);
  };

  const closeModal = () => {
    setShowCreateModal(false);
    setEditingDivision(null);
    setFormData(emptyDivisionForm);
  };

  const submitDivision = async (e) => {
    e.preventDefault();
    try {
      if (editingDivision) {
        await axios.put(`/api/divisions/${editingDivision.id}`, formData);
        toast.success('Division updated');
      } else {
        await axios.post('/api/divisions/', formData);
        toast.success('Division created');
      }
      closeModal();
      fetchDivisions();
      fetchStats();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save division');
    }
  };

  const deleteDivision = async (divisionId) => {
    if (!window.confirm('Delete this division?')) return;
    try {
      await axios.delete(`/api/divisions/${divisionId}`);
      toast.success('Division deleted');
      fetchDivisions();
      fetchStats();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to delete division');
    }
  };

  const filteredDivisions = divisions.filter(division => {
    if (searchTerm) {
      const search = searchTerm.toLowerCase();
      if (!division.name.toLowerCase().includes(search) && 
          !division.description?.toLowerCase().includes(search)) {
        return false;
      }
    }
    
    if (filters.organization_id && division.organization_id !== filters.organization_id) return false;
    if (filters.type && division.type !== filters.type) return false;
    if (filters.status && division.status !== filters.status) return false;
    
    return true;
  });

  const getStatusColor = (status) => {
    const colors = {
      'Active': 'bg-green-100 text-green-800',
      'Available': 'bg-blue-100 text-blue-800',
      'Overloaded': 'bg-red-100 text-red-800',
      'Inactive': 'bg-gray-100 text-gray-800'
    };
    return colors[status] || colors['Available'];
  };

  const getTypeColor = (type) => {
    const colors = {
      'Medical': 'bg-blue-100 text-blue-800',
      'Rescue': 'bg-red-100 text-red-800',
      'Logistics': 'bg-yellow-100 text-yellow-800',
      'Communication': 'bg-purple-100 text-purple-800',
      'Emergency Response': 'bg-orange-100 text-orange-800'
    };
    return colors[type] || colors['Emergency Response'];
  };

  const getOrganizationName = (orgId) => {
    const org = organizations.find(o => o.id === orgId);
    return org ? org.name : 'Unknown';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Divisions</h1>
          <p className="text-gray-600">Manage organizational divisions and track their workload</p>
        </div>
        <button
          onClick={openCreateModal}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2"
        >
          <Plus className="w-5 h-5" />
          <span>Add Division</span>
        </button>
      </div>

      {/* Statistics Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
          <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Total Divisions</p>
                <p className="text-2xl font-bold text-gray-900">{stats.total_divisions}</p>
              </div>
              <Activity className="w-8 h-8 text-blue-600" />
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Active Divisions</p>
                <p className="text-2xl font-bold text-gray-900">{stats.active_divisions}</p>
              </div>
              <CheckCircle className="w-8 h-8 text-green-600" />
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Total Capacity</p>
                <p className="text-2xl font-bold text-gray-900">{stats.total_capacity}</p>
              </div>
              <Users className="w-8 h-8 text-orange-600" />
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Utilization Rate</p>
                <p className="text-2xl font-bold text-gray-900">{stats.utilization_rate}%</p>
              </div>
              <TrendingUp className="w-8 h-8 text-purple-600" />
            </div>
          </div>
        </div>
      )}

      {/* Filters and Search */}
      <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200 mb-6">
        <div className="flex flex-col lg:flex-row gap-4">
          {/* Search */}
          <div className="flex-1">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
              <input
                type="text"
                placeholder="Search divisions..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>

          {/* Filters */}
          <div className="flex gap-4">
            <select
              value={filters.organization_id}
              onChange={(e) => setFilters({ ...filters, organization_id: e.target.value })}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="">All Organizations</option>
              {organizations.map(org => (
                <option key={org.id} value={org.id}>{org.name}</option>
              ))}
            </select>

            <select
              value={filters.type}
              onChange={(e) => setFilters({ ...filters, type: e.target.value })}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="">All Types</option>
              <option value="Medical">Medical</option>
              <option value="Rescue">Rescue</option>
              <option value="Logistics">Logistics</option>
              <option value="Communication">Communication</option>
              <option value="Emergency Response">Emergency Response</option>
            </select>

            <select
              value={filters.status}
              onChange={(e) => setFilters({ ...filters, status: e.target.value })}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="">All Statuses</option>
              <option value="Active">Active</option>
              <option value="Available">Available</option>
              <option value="Overloaded">Overloaded</option>
              <option value="Inactive">Inactive</option>
            </select>
          </div>
        </div>
      </div>

      {/* Divisions Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredDivisions.map((division) => (
          <div key={division.id} className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
            {/* Header */}
            <div className="p-6 border-b border-gray-200">
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">{division.name}</h3>
                  <div className="flex flex-wrap gap-2 mb-3">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getTypeColor(division.type)}`}>
                      {division.type}
                    </span>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(division.status)}`}>
                      {division.status}
                    </span>
                  </div>
                </div>
                <div className="flex space-x-2">
                  <button
                    onClick={() => openEditModal(division)}
                    className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                  >
                    <Edit className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => deleteDivision(division.id)}
                    className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Organization */}
              <div className="space-y-2 text-sm text-gray-600 mb-3">
                <div className="flex items-center space-x-2">
                  <Building2 className="w-4 h-4" />
                  <span>{getOrganizationName(division.organization_id)}</span>
                </div>
                {division.description && (
                  <div className="text-sm text-gray-600">
                    <p>{division.description}</p>
                  </div>
                )}
              </div>
            </div>

            {/* Capacity and Load */}
            <div className="p-6 bg-gray-50">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-gray-700">Capacity</span>
                <span className="text-sm text-gray-600">{division.current_load} / {division.capacity}</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className={`h-2 rounded-full ${
                    division.current_load >= division.capacity ? 'bg-red-500' :
                    division.current_load > division.capacity * 0.8 ? 'bg-yellow-500' : 'bg-green-500'
                  }`}
                  style={{ width: `${division.capacity > 0 ? Math.min((division.current_load / division.capacity) * 100, 100) : 0}%` }}
                ></div>
              </div>
              <div className="flex items-center justify-between mt-2">
                <span className="text-xs text-gray-500">Utilization</span>
                <span className="text-xs font-medium text-gray-700">
                  {division.capacity > 0 ? Math.round((division.current_load / division.capacity) * 100) : 0}%
                </span>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="p-4 bg-white border-t border-gray-200">
              <div className="flex space-x-2">
                <button className="flex-1 px-3 py-2 text-sm bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 transition-colors">
                  View Staff
                </button>
                <button className="flex-1 px-3 py-2 text-sm bg-green-50 text-green-700 rounded-lg hover:bg-green-100 transition-colors">
                  View Workload
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {filteredDivisions.length === 0 && (
        <div className="text-center py-12">
          <Activity className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No divisions found</h3>
          <p className="text-gray-600">Try adjusting your search or filters</p>
        </div>
      )}

      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <form onSubmit={submitDivision} className="bg-white rounded-lg shadow-xl w-full max-w-2xl p-6 space-y-4">
            <h3 className="text-xl font-semibold text-gray-900">{editingDivision ? 'Edit Division' : 'Create Division'}</h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <input className="border rounded-lg px-3 py-2" placeholder="Name" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} required />
              <select
                className="border rounded-lg px-3 py-2"
                value={formData.organization_id}
                onChange={(e) => setFormData({ ...formData, organization_id: e.target.value })}
                required
              >
                <option value="">Select Organization</option>
                {organizations.map(org => (
                  <option key={org.id} value={org.id}>{org.name}</option>
                ))}
              </select>
              <select className="border rounded-lg px-3 py-2" value={formData.type} onChange={(e) => setFormData({ ...formData, type: e.target.value })}>
                <option value="Medical">Medical</option>
                <option value="Rescue">Rescue</option>
                <option value="Logistics">Logistics</option>
                <option value="Communication">Communication</option>
                <option value="Emergency Response">Emergency Response</option>
              </select>
              <input type="number" min="0" className="border rounded-lg px-3 py-2" placeholder="Capacity" value={formData.capacity} onChange={(e) => setFormData({ ...formData, capacity: parseInt(e.target.value || '0', 10) })} />
              <input type="number" min="0" className="border rounded-lg px-3 py-2" placeholder="Current Load" value={formData.current_load} onChange={(e) => setFormData({ ...formData, current_load: parseInt(e.target.value || '0', 10) })} />
              <select className="border rounded-lg px-3 py-2" value={formData.status} onChange={(e) => setFormData({ ...formData, status: e.target.value })}>
                <option value="Active">Active</option>
                <option value="Available">Available</option>
                <option value="Overloaded">Overloaded</option>
                <option value="Inactive">Inactive</option>
              </select>
              <textarea
                className="border rounded-lg px-3 py-2 md:col-span-2"
                rows={3}
                placeholder="Description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              />
            </div>

            <div className="flex justify-end space-x-3 pt-2">
              <button type="button" onClick={closeModal} className="px-4 py-2 rounded-lg bg-gray-100 text-gray-700 hover:bg-gray-200">
                Cancel
              </button>
              <button type="submit" className="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700">
                {editingDivision ? 'Save Changes' : 'Create'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};

export default Divisions;
