import React, { useState, useEffect } from 'react';
import { 
  Building2, 
  Users, 
  MapPin, 
  Phone, 
  Mail, 
  Plus, 
  Edit, 
  Trash2, 
  Search,
  TrendingUp,
  Activity
} from 'lucide-react';
import axios from 'axios';
import toast from 'react-hot-toast';

const emptyOrgForm = {
  name: '',
  type: 'Government',
  category: 'Emergency Response',
  address: '',
  contact_person: '',
  contact_phone: '',
  contact_email: '',
  capacity: 100,
  current_load: 0,
  status: 'Active'
};

const Organizations = () => {
  const [organizations, setOrganizations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [filters, setFilters] = useState({
    type: '',
    category: '',
    status: ''
  });
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingOrg, setEditingOrg] = useState(null);
  const [stats, setStats] = useState(null);
  const [formData, setFormData] = useState(emptyOrgForm);

  useEffect(() => {
    fetchOrganizations();
    fetchStats();
  }, []);

  const fetchOrganizations = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/organizations/');
      setOrganizations(response.data);
    } catch (error) {
      toast.error('Failed to fetch organizations');
      console.error('Error fetching organizations:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await axios.get('/api/organizations/overview/stats');
      setStats(response.data);
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  };

  const openCreateModal = () => {
    setEditingOrg(null);
    setFormData(emptyOrgForm);
    setShowCreateModal(true);
  };

  const openEditModal = (org) => {
    setEditingOrg(org);
    setFormData({
      name: org.name || '',
      type: org.type || 'Government',
      category: org.category || 'Emergency Response',
      address: org.address || '',
      contact_person: org.contact_person || '',
      contact_phone: org.contact_phone || '',
      contact_email: org.contact_email || '',
      capacity: org.capacity || 0,
      current_load: org.current_load || 0,
      status: org.status || 'Active'
    });
    setShowCreateModal(true);
  };

  const closeModal = () => {
    setShowCreateModal(false);
    setEditingOrg(null);
    setFormData(emptyOrgForm);
  };

  const submitOrganization = async (e) => {
    e.preventDefault();
    try {
      if (editingOrg) {
        await axios.put(`/api/organizations/${editingOrg.id}`, formData);
        toast.success('Organization updated');
      } else {
        await axios.post('/api/organizations/', formData);
        toast.success('Organization created');
      }
      closeModal();
      fetchOrganizations();
      fetchStats();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save organization');
    }
  };

  const deleteOrganization = async (orgId) => {
    if (!window.confirm('Delete this organization?')) return;
    try {
      await axios.delete(`/api/organizations/${orgId}`);
      toast.success('Organization deleted');
      fetchOrganizations();
      fetchStats();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to delete organization');
    }
  };

  const filteredOrganizations = organizations.filter(org => {
    if (searchTerm) {
      const search = searchTerm.toLowerCase();
      if (!org.name.toLowerCase().includes(search) && 
          !org.address?.toLowerCase().includes(search)) {
        return false;
      }
    }
    
    if (filters.type && org.type !== filters.type) return false;
    if (filters.category && org.category !== filters.category) return false;
    if (filters.status && org.status !== filters.status) return false;
    
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
      'Government': 'bg-purple-100 text-purple-800',
      'NGO': 'bg-orange-100 text-orange-800',
      'Volunteer Group': 'bg-pink-100 text-pink-800',
      'Private': 'bg-indigo-100 text-indigo-800'
    };
    return colors[type] || colors['Private'];
  };

  const getCategoryColor = (category) => {
    const colors = {
      'Emergency Response': 'bg-red-100 text-red-800',
      'Medical': 'bg-blue-100 text-blue-800',
      'Relief': 'bg-green-100 text-green-800',
      'Logistics': 'bg-yellow-100 text-yellow-800'
    };
    return colors[category] || colors['Emergency Response'];
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
          <h1 className="text-3xl font-bold text-gray-900">Organizations</h1>
          <p className="text-gray-600">Manage disaster response organizations and their capacity</p>
        </div>
        <button
          onClick={openCreateModal}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2"
        >
          <Plus className="w-5 h-5" />
          <span>Add Organization</span>
        </button>
      </div>

      {/* Statistics Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
          <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Total Organizations</p>
                <p className="text-2xl font-bold text-gray-900">{stats.total_organizations}</p>
              </div>
              <Building2 className="w-8 h-8 text-blue-600" />
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Total Capacity</p>
                <p className="text-2xl font-bold text-gray-900">{stats.total_capacity}</p>
              </div>
              <Users className="w-8 h-8 text-green-600" />
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Current Load</p>
                <p className="text-2xl font-bold text-gray-900">{stats.current_load}</p>
              </div>
              <Activity className="w-8 h-8 text-orange-600" />
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
                placeholder="Search organizations..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>

          {/* Filters */}
          <div className="flex gap-4">
            <select
              value={filters.type}
              onChange={(e) => setFilters({ ...filters, type: e.target.value })}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="">All Types</option>
              <option value="Government">Government</option>
              <option value="NGO">NGO</option>
              <option value="Volunteer Group">Volunteer Group</option>
              <option value="Private">Private</option>
            </select>

            <select
              value={filters.category}
              onChange={(e) => setFilters({ ...filters, category: e.target.value })}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="">All Categories</option>
              <option value="Emergency Response">Emergency Response</option>
              <option value="Medical">Medical</option>
              <option value="Relief">Relief</option>
              <option value="Logistics">Logistics</option>
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

      {/* Organizations Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredOrganizations.map((org) => (
          <div key={org.id} className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
            {/* Header */}
            <div className="p-6 border-b border-gray-200">
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">{org.name}</h3>
                  <div className="flex flex-wrap gap-2 mb-3">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getTypeColor(org.type)}`}>
                      {org.type}
                    </span>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getCategoryColor(org.category)}`}>
                      {org.category}
                    </span>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(org.status)}`}>
                      {org.status}
                    </span>
                  </div>
                </div>
                <div className="flex space-x-2">
                  <button
                    onClick={() => openEditModal(org)}
                    className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                  >
                    <Edit className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => deleteOrganization(org.id)}
                    className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Contact Info */}
              <div className="space-y-2 text-sm text-gray-600">
                {org.contact_person && (
                  <div className="flex items-center space-x-2">
                    <Users className="w-4 h-4" />
                    <span>{org.contact_person}</span>
                  </div>
                )}
                {org.address && (
                  <div className="flex items-center space-x-2">
                    <MapPin className="w-4 h-4" />
                    <span>{org.address}</span>
                  </div>
                )}
                {org.contact_phone && (
                  <div className="flex items-center space-x-2">
                    <Phone className="w-4 h-4" />
                    <span>{org.contact_phone}</span>
                  </div>
                )}
                {org.contact_email && (
                  <div className="flex items-center space-x-2">
                    <Mail className="w-4 h-4" />
                    <span>{org.contact_email}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Capacity and Load */}
            <div className="p-6 bg-gray-50">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-gray-700">Capacity</span>
                <span className="text-sm text-gray-600">{org.current_load} / {org.capacity}</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className={`h-2 rounded-full ${
                    org.current_load >= org.capacity ? 'bg-red-500' :
                    org.current_load > org.capacity * 0.8 ? 'bg-yellow-500' : 'bg-green-500'
                  }`}
                  style={{ width: `${org.capacity > 0 ? Math.min((org.current_load / org.capacity) * 100, 100) : 0}%` }}
                ></div>
              </div>
              <div className="flex items-center justify-between mt-2">
                <span className="text-xs text-gray-500">Utilization</span>
                <span className="text-xs font-medium text-gray-700">
                  {org.capacity > 0 ? Math.round((org.current_load / org.capacity) * 100) : 0}%
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {filteredOrganizations.length === 0 && (
        <div className="text-center py-12">
          <Building2 className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No organizations found</h3>
          <p className="text-gray-600">Try adjusting your search or filters</p>
        </div>
      )}

      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <form onSubmit={submitOrganization} className="bg-white rounded-lg shadow-xl w-full max-w-2xl p-6 space-y-4">
            <h3 className="text-xl font-semibold text-gray-900">
              {editingOrg ? 'Edit Organization' : 'Create Organization'}
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <input className="border rounded-lg px-3 py-2" placeholder="Name" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} required />
              <input className="border rounded-lg px-3 py-2" placeholder="Address" value={formData.address} onChange={(e) => setFormData({ ...formData, address: e.target.value })} />
              <select className="border rounded-lg px-3 py-2" value={formData.type} onChange={(e) => setFormData({ ...formData, type: e.target.value })}>
                <option value="Government">Government</option>
                <option value="NGO">NGO</option>
                <option value="Volunteer Group">Volunteer Group</option>
                <option value="Private">Private</option>
              </select>
              <select className="border rounded-lg px-3 py-2" value={formData.category} onChange={(e) => setFormData({ ...formData, category: e.target.value })}>
                <option value="Emergency Response">Emergency Response</option>
                <option value="Medical">Medical</option>
                <option value="Relief">Relief</option>
                <option value="Logistics">Logistics</option>
                <option value="Rescue">Rescue</option>
              </select>
              <input className="border rounded-lg px-3 py-2" placeholder="Contact Person" value={formData.contact_person} onChange={(e) => setFormData({ ...formData, contact_person: e.target.value })} />
              <input className="border rounded-lg px-3 py-2" placeholder="Contact Phone" value={formData.contact_phone} onChange={(e) => setFormData({ ...formData, contact_phone: e.target.value })} />
              <input className="border rounded-lg px-3 py-2" placeholder="Contact Email" value={formData.contact_email} onChange={(e) => setFormData({ ...formData, contact_email: e.target.value })} />
              <input type="number" min="0" className="border rounded-lg px-3 py-2" placeholder="Capacity" value={formData.capacity} onChange={(e) => setFormData({ ...formData, capacity: parseInt(e.target.value || '0', 10) })} />
              <input type="number" min="0" className="border rounded-lg px-3 py-2" placeholder="Current Load" value={formData.current_load} onChange={(e) => setFormData({ ...formData, current_load: parseInt(e.target.value || '0', 10) })} />
              <select className="border rounded-lg px-3 py-2" value={formData.status} onChange={(e) => setFormData({ ...formData, status: e.target.value })}>
                <option value="Active">Active</option>
                <option value="Available">Available</option>
                <option value="Overloaded">Overloaded</option>
                <option value="Inactive">Inactive</option>
              </select>
            </div>

            <div className="flex justify-end space-x-3 pt-2">
              <button type="button" onClick={closeModal} className="px-4 py-2 rounded-lg bg-gray-100 text-gray-700 hover:bg-gray-200">
                Cancel
              </button>
              <button type="submit" className="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700">
                {editingOrg ? 'Save Changes' : 'Create'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};

export default Organizations;
