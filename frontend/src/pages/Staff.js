import React, { useState, useEffect } from 'react';
import { 
  Users, 
  MapPin, 
  Phone, 
  Mail, 
  Plus, 
  Edit, 
  Trash2, 
  Search,
  TrendingUp,
  Activity,
  CheckCircle
} from 'lucide-react';
import axios from 'axios';
import toast from 'react-hot-toast';

const emptyStaffForm = {
  name: '',
  organization_id: '',
  division_id: '',
  role: 'Worker',
  skills: '',
  contact_phone: '',
  contact_email: '',
  availability: 'Available',
  current_location: '',
  status: 'Active'
};

const Staff = () => {
  const [staff, setStaff] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [filters, setFilters] = useState({
    organization_id: '',
    division_id: '',
    role: '',
    availability: '',
    status: ''
  });
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingStaff, setEditingStaff] = useState(null);
  const [stats, setStats] = useState(null);
  const [organizations, setOrganizations] = useState([]);
  const [divisions, setDivisions] = useState([]);
  const [formData, setFormData] = useState(emptyStaffForm);

  useEffect(() => {
    fetchStaff();
    fetchStats();
    fetchOrganizations();
  }, []);

  useEffect(() => {
    if (filters.organization_id) {
      fetchDivisions(filters.organization_id);
    }
  }, [filters.organization_id]);

  const fetchStaff = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/staff/');
      setStaff(response.data);
    } catch (error) {
      toast.error('Failed to fetch staff');
      console.error('Error fetching staff:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await axios.get('/api/staff/overview/stats');
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

  const fetchDivisions = async (orgId) => {
    try {
      const response = await axios.get(`/api/divisions/?organization_id=${orgId}`);
      setDivisions(response.data);
    } catch (error) {
      console.error('Error fetching divisions:', error);
    }
  };

  const openCreateModal = () => {
    setEditingStaff(null);
    setFormData(emptyStaffForm);
    setShowCreateModal(true);
  };

  const openEditModal = async (member) => {
    if (member.organization_id) {
      await fetchDivisions(member.organization_id);
    }
    setEditingStaff(member);
    setFormData({
      name: member.name || '',
      organization_id: member.organization_id || '',
      division_id: member.division_id || '',
      role: member.role || 'Worker',
      skills: member.skills || '',
      contact_phone: member.contact_phone || '',
      contact_email: member.contact_email || '',
      availability: member.availability || 'Available',
      current_location: member.current_location || '',
      status: member.status || 'Active'
    });
    setShowCreateModal(true);
  };

  const closeModal = () => {
    setShowCreateModal(false);
    setEditingStaff(null);
    setFormData(emptyStaffForm);
  };

  const submitStaff = async (e) => {
    e.preventDefault();
    try {
      if (editingStaff) {
        await axios.put(`/api/staff/${editingStaff.id}`, formData);
        toast.success('Staff updated');
      } else {
        await axios.post('/api/staff/', formData);
        toast.success('Staff created');
      }
      closeModal();
      fetchStaff();
      fetchStats();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save staff');
    }
  };

  const deleteStaff = async (staffId) => {
    if (!window.confirm('Delete this staff member?')) return;
    try {
      await axios.delete(`/api/staff/${staffId}`);
      toast.success('Staff deleted');
      fetchStaff();
      fetchStats();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to delete staff');
    }
  };

  const filteredStaff = staff.filter(member => {
    if (searchTerm) {
      const search = searchTerm.toLowerCase();
      if (!member.name.toLowerCase().includes(search) && 
          !member.current_location?.toLowerCase().includes(search)) {
        return false;
      }
    }
    
    if (filters.organization_id && member.organization_id !== filters.organization_id) return false;
    if (filters.division_id && member.division_id !== filters.division_id) return false;
    if (filters.role && member.role !== filters.role) return false;
    if (filters.availability && member.availability !== filters.availability) return false;
    if (filters.status && member.status !== filters.status) return false;
    
    return true;
  });

  const getStatusColor = (status) => {
    const colors = {
      'Active': 'bg-green-100 text-green-800',
      'Inactive': 'bg-gray-100 text-gray-800'
    };
    return colors[status] || colors['Active'];
  };

  const getAvailabilityColor = (availability) => {
    const colors = {
      'Available': 'bg-green-100 text-green-800',
      'Busy': 'bg-yellow-100 text-yellow-800',
      'Off-duty': 'bg-red-100 text-red-800'
    };
    return colors[availability] || colors['Available'];
  };

  const getRoleColor = (role) => {
    const colors = {
      'Manager': 'bg-purple-100 text-purple-800',
      'Specialist': 'bg-blue-100 text-blue-800',
      'Worker': 'bg-orange-100 text-orange-800',
      'Volunteer': 'bg-pink-100 text-pink-800'
    };
    return colors[role] || colors['Worker'];
  };

  const getOrganizationName = (orgId) => {
    const org = organizations.find(o => o.id === orgId);
    return org ? org.name : 'Unknown';
  };

  const getDivisionName = (divId) => {
    const div = divisions.find(d => d.id === divId);
    return div ? div.name : 'None';
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
          <h1 className="text-3xl font-bold text-gray-900">Staff Management</h1>
          <p className="text-gray-600">Manage disaster response staff and track their availability</p>
        </div>
        <button
          onClick={openCreateModal}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2"
        >
          <Plus className="w-5 h-5" />
          <span>Add Staff Member</span>
        </button>
      </div>

      {/* Statistics Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
          <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Total Staff</p>
                <p className="text-2xl font-bold text-gray-900">{stats.total_staff}</p>
              </div>
              <Users className="w-8 h-8 text-blue-600" />
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Active Staff</p>
                <p className="text-2xl font-bold text-gray-900">{stats.active_staff}</p>
              </div>
              <CheckCircle className="w-8 h-8 text-green-600" />
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Available Staff</p>
                <p className="text-2xl font-bold text-gray-900">{stats.available_staff}</p>
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
                placeholder="Search staff members..."
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
              onChange={(e) => {
                setFilters({ ...filters, organization_id: e.target.value, division_id: '' });
                setDivisions([]);
              }}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="">All Organizations</option>
              {organizations.map(org => (
                <option key={org.id} value={org.id}>{org.name}</option>
              ))}
            </select>

            <select
              value={filters.division_id}
              onChange={(e) => setFilters({ ...filters, division_id: e.target.value })}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={!filters.organization_id}
            >
              <option value="">All Divisions</option>
              {divisions.map(div => (
                <option key={div.id} value={div.id}>{div.name}</option>
              ))}
            </select>

            <select
              value={filters.role}
              onChange={(e) => setFilters({ ...filters, role: e.target.value })}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="">All Roles</option>
              <option value="Manager">Manager</option>
              <option value="Specialist">Specialist</option>
              <option value="Worker">Worker</option>
              <option value="Volunteer">Volunteer</option>
            </select>

            <select
              value={filters.availability}
              onChange={(e) => setFilters({ ...filters, availability: e.target.value })}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="">All Availability</option>
              <option value="Available">Available</option>
              <option value="Busy">Busy</option>
              <option value="Off-duty">Off-duty</option>
            </select>

            <select
              value={filters.status}
              onChange={(e) => setFilters({ ...filters, status: e.target.value })}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="">All Statuses</option>
              <option value="Active">Active</option>
              <option value="Inactive">Inactive</option>
            </select>
          </div>
        </div>
      </div>

      {/* Staff Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredStaff.map((member) => (
          <div key={member.id} className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
            {/* Header */}
            <div className="p-6 border-b border-gray-200">
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">{member.name}</h3>
                  <div className="flex flex-wrap gap-2 mb-3">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getRoleColor(member.role)}`}>
                      {member.role}
                    </span>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getAvailabilityColor(member.availability)}`}>
                      {member.availability}
                    </span>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(member.status)}`}>
                      {member.status}
                    </span>
                  </div>
                </div>
                <div className="flex space-x-2">
                  <button
                    onClick={() => openEditModal(member)}
                    className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                  >
                    <Edit className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => deleteStaff(member.id)}
                    className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Organization & Division */}
              <div className="space-y-2 text-sm text-gray-600 mb-3">
                <div className="flex items-center space-x-2">
                  <Users className="w-4 h-4" />
                  <span>{getOrganizationName(member.organization_id)}</span>
                </div>
                {member.division_id && (
                  <div className="flex items-center space-x-2">
                    <Activity className="w-4 h-4" />
                    <span>{getDivisionName(member.division_id)}</span>
                  </div>
                )}
                {member.current_location && (
                  <div className="flex items-center space-x-2">
                    <MapPin className="w-4 h-4" />
                    <span>{member.current_location}</span>
                  </div>
                )}
              </div>

              {/* Contact Info */}
              <div className="space-y-2 text-sm text-gray-600">
                {member.contact_phone && (
                  <div className="flex items-center space-x-2">
                    <Phone className="w-4 h-4" />
                    <span>{member.contact_phone}</span>
                  </div>
                )}
                {member.contact_email && (
                  <div className="flex items-center space-x-2">
                    <Mail className="w-4 h-4" />
                    <span>{member.contact_email}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Skills */}
            {member.skills && (
              <div className="p-4 bg-gray-50 border-b border-gray-200">
                <h4 className="text-sm font-medium text-gray-700 mb-2">Skills</h4>
                <div className="flex flex-wrap gap-1">
                  {member.skills.split(',').map((skill, index) => (
                    <span 
                      key={index}
                      className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full"
                    >
                      {skill.trim()}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Workload Indicator */}
            <div className="p-4 bg-gray-50">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-700">Current Status</span>
                <div className="flex items-center space-x-2">
                  {member.availability === 'Available' && (
                    <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  )}
                  {member.availability === 'Busy' && (
                    <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
                  )}
                  {member.availability === 'Off-duty' && (
                    <div className="w-2 h-2 bg-red-500 rounded-full"></div>
                  )}
                  <span className="text-xs text-gray-600">{member.availability}</span>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {filteredStaff.length === 0 && (
        <div className="text-center py-12">
          <Users className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No staff members found</h3>
          <p className="text-gray-600">Try adjusting your search or filters</p>
        </div>
      )}

      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <form onSubmit={submitStaff} className="bg-white rounded-lg shadow-xl w-full max-w-3xl p-6 space-y-4">
            <h3 className="text-xl font-semibold text-gray-900">{editingStaff ? 'Edit Staff Member' : 'Create Staff Member'}</h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <input className="border rounded-lg px-3 py-2" placeholder="Name" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} required />
              <select
                className="border rounded-lg px-3 py-2"
                value={formData.organization_id}
                onChange={(e) => {
                  const orgId = e.target.value;
                  setFormData({ ...formData, organization_id: orgId, division_id: '' });
                  if (orgId) fetchDivisions(orgId);
                }}
                required
              >
                <option value="">Select Organization</option>
                {organizations.map(org => (
                  <option key={org.id} value={org.id}>{org.name}</option>
                ))}
              </select>
              <select className="border rounded-lg px-3 py-2" value={formData.division_id} onChange={(e) => setFormData({ ...formData, division_id: e.target.value })}>
                <option value="">No Division</option>
                {divisions.map(div => (
                  <option key={div.id} value={div.id}>{div.name}</option>
                ))}
              </select>
              <select className="border rounded-lg px-3 py-2" value={formData.role} onChange={(e) => setFormData({ ...formData, role: e.target.value })}>
                <option value="Manager">Manager</option>
                <option value="Specialist">Specialist</option>
                <option value="Worker">Worker</option>
                <option value="Volunteer">Volunteer</option>
              </select>
              <input className="border rounded-lg px-3 py-2" placeholder="Skills (comma separated)" value={formData.skills} onChange={(e) => setFormData({ ...formData, skills: e.target.value })} />
              <input className="border rounded-lg px-3 py-2" placeholder="Phone" value={formData.contact_phone} onChange={(e) => setFormData({ ...formData, contact_phone: e.target.value })} />
              <input className="border rounded-lg px-3 py-2" placeholder="Email" value={formData.contact_email} onChange={(e) => setFormData({ ...formData, contact_email: e.target.value })} />
              <input className="border rounded-lg px-3 py-2" placeholder="Current Location" value={formData.current_location} onChange={(e) => setFormData({ ...formData, current_location: e.target.value })} />
              <select className="border rounded-lg px-3 py-2" value={formData.availability} onChange={(e) => setFormData({ ...formData, availability: e.target.value })}>
                <option value="Available">Available</option>
                <option value="Busy">Busy</option>
                <option value="Off-duty">Off-duty</option>
              </select>
              <select className="border rounded-lg px-3 py-2" value={formData.status} onChange={(e) => setFormData({ ...formData, status: e.target.value })}>
                <option value="Active">Active</option>
                <option value="Inactive">Inactive</option>
              </select>
            </div>

            <div className="flex justify-end space-x-3 pt-2">
              <button type="button" onClick={closeModal} className="px-4 py-2 rounded-lg bg-gray-100 text-gray-700 hover:bg-gray-200">
                Cancel
              </button>
              <button type="submit" className="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700">
                {editingStaff ? 'Save Changes' : 'Create'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};

export default Staff;
