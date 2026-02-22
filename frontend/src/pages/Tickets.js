import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Building,
  CheckCircle,
  Clock,
  Edit,
  Heart,
  MapPin,
  Navigation,
  Plus,
  Search,
  Trash2,
  Users,
} from 'lucide-react';
import axios from 'axios';
import toast from 'react-hot-toast';
import TicketModal from '../components/TicketModal';
import { useAuth } from '../contexts/AuthContext';
import { SOS_CHANGED_EVENT } from '../utils/sosRealtime';

const NEW_TICKET_STATUSES = ['Pending', 'Pending Assignment'];
const ONGOING_TICKET_STATUSES = ['In Progress'];
const SERVED_TICKET_STATUSES = ['Done'];

const LIFECYCLE_FILTERS = [
  { id: 'new', label: 'New Tickets', statuses: NEW_TICKET_STATUSES, badge: 'bg-yellow-100 text-yellow-700' },
  { id: 'ongoing', label: 'Ongoing Tickets', statuses: ONGOING_TICKET_STATUSES, badge: 'bg-blue-100 text-blue-700' },
  { id: 'served', label: 'Served Tickets', statuses: SERVED_TICKET_STATUSES, badge: 'bg-green-100 text-green-700' },
];

const EMPTY_STAFF = Object.freeze({});

const parseServerDateTime = (value) => {
  const raw = (value ?? '').toString().trim();
  if (!raw) return null;
  const hasTimezone = /(z|[+-]\d{2}:?\d{2})$/i.test(raw);
  const normalized = hasTimezone ? raw : `${raw}Z`;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
};

const formatTicketReportedAt = (ticket) => {
  const date = parseServerDateTime(ticket?.timestamp || ticket?.created_at);
  if (!date) return 'N/A';
  return date.toLocaleString();
};

const Tickets = () => {
  const { user } = useAuth();
  const canEdit = user?.role === 'admin' || user?.role === 'responder';
  const isAdmin = user?.role === 'admin';

  const [tickets, setTickets] = useState([]);
  const [staffLookup, setStaffLookup] = useState(EMPTY_STAFF);
  const [filteredTickets, setFilteredTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creatingTicket, setCreatingTicket] = useState(false);
  const [activeLifecycle, setActiveLifecycle] = useState('new');

  const [newTicket, setNewTicket] = useState({
    people: 1,
    longitude: 78.4867,
    latitude: 17.385,
    text: '',
    place: '',
    category: 'General Emergency',
  });

  const [filters, setFilters] = useState({
    status: '',
    category: '',
    priority: '',
    region: '',
  });
  const [searchTerm, setSearchTerm] = useState('');

  const fetchTickets = useCallback(async (options = { silent: false }) => {
    const silent = Boolean(options?.silent);
    try {
      if (!silent) {
        setLoading(true);
      }
      const [ticketsRes, staffRes] = await Promise.all([
        axios.get('/api/sos/'),
        axios.get('/api/staff/').catch(() => ({ data: [] })),
      ]);

      const nextTickets = Array.isArray(ticketsRes.data) ? ticketsRes.data : [];
      const staff = Array.isArray(staffRes.data) ? staffRes.data : [];
      const lookup = staff.reduce((acc, member) => {
        if (member?.id) {
          acc[member.id] = member.name || member.id;
        }
        return acc;
      }, {});

      setTickets(nextTickets);
      setStaffLookup(Object.keys(lookup).length > 0 ? lookup : EMPTY_STAFF);
    } catch (error) {
      if (!silent) {
        toast.error('Failed to fetch tickets');
      }
      console.error('Tickets fetch error:', error);
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    fetchTickets();
    const timer = setInterval(() => {
      fetchTickets({ silent: true });
    }, 30000);

    const onSosChanged = () => {
      fetchTickets({ silent: true });
    };
    window.addEventListener(SOS_CHANGED_EVENT, onSosChanged);

    return () => {
      clearInterval(timer);
      window.removeEventListener(SOS_CHANGED_EVENT, onSosChanged);
    };
  }, [fetchTickets]);

  const applyFilters = useCallback(() => {
    let filtered = [...tickets];

    if (searchTerm) {
      const needle = searchTerm.toLowerCase();
      filtered = filtered.filter((ticket) =>
        `${ticket.place || ''} ${ticket.text || ''} ${ticket.category || ''}`.toLowerCase().includes(needle)
      );
    }

    if (filters.status) {
      filtered = filtered.filter((ticket) => ticket.status === filters.status);
    }

    if (filters.category) {
      filtered = filtered.filter((ticket) => ticket.category === filters.category);
    }

    if (filters.priority) {
      filtered = filtered.filter((ticket) => ticket.priority === parseInt(filters.priority, 10));
    }

    if (filters.region) {
      filtered = filtered.filter((ticket) => {
        const lon = ticket.longitude;
        if (filters.region === 'south') return lon >= 77.0 && lon <= 78.4;
        if (filters.region === 'central') return lon >= 78.4 && lon <= 79.6;
        if (filters.region === 'north') return lon >= 79.6 && lon <= 81.0;
        return true;
      });
    }

    setFilteredTickets(filtered);
  }, [tickets, filters, searchTerm]);

  useEffect(() => {
    applyFilters();
  }, [applyFilters]);

  const lifecycleBuckets = useMemo(() => {
    const byId = { new: [], ongoing: [], served: [] };
    filteredTickets.forEach((ticket) => {
      if (NEW_TICKET_STATUSES.includes(ticket.status)) {
        byId.new.push(ticket);
      } else if (ONGOING_TICKET_STATUSES.includes(ticket.status)) {
        byId.ongoing.push(ticket);
      } else if (SERVED_TICKET_STATUSES.includes(ticket.status)) {
        byId.served.push(ticket);
      }
    });
    return byId;
  }, [filteredTickets]);

  const activeLifecycleConfig = LIFECYCLE_FILTERS.find((item) => item.id === activeLifecycle) || LIFECYCLE_FILTERS[0];
  const visibleTickets = lifecycleBuckets[activeLifecycleConfig.id] || [];

  const categories = useMemo(() => [...new Set(tickets.map((ticket) => ticket.category).filter(Boolean))], [tickets]);
  const regions = [
    { value: 'south', label: 'South Telangana' },
    { value: 'central', label: 'Central Telangana' },
    { value: 'north', label: 'North Telangana' },
  ];

  const handleTicketClick = (ticket) => {
    const assignedName = ticket.assigned_to ? staffLookup[ticket.assigned_to] || ticket.assigned_to : null;
    setSelectedTicket({ ...ticket, assigned_to_name: assignedName });
    setShowModal(true);
  };

  const handleStatusUpdate = async (ticketId, newStatus, notes) => {
    if (!canEdit) {
      toast.error('Read-only access: viewers cannot update tickets');
      return;
    }

    try {
      await axios.put(`/api/sos/${ticketId}`, {
        status: newStatus,
        notes,
      });

      setTickets((prev) =>
        prev.map((ticket) =>
          ticket.id === ticketId
            ? {
                ...ticket,
                status: newStatus,
                notes,
              }
            : ticket,
        ),
      );

      toast.success('Ticket status updated successfully');
      setShowModal(false);
    } catch (error) {
      toast.error('Failed to update ticket status');
      console.error('Status update error:', error);
    }
  };

  const handleCreateTicket = async () => {
    if (!isAdmin) {
      toast.error('Only admins can create tickets');
      return;
    }

    if (!newTicket.text || !newTicket.place || !newTicket.category) {
      toast.error('Please fill all required fields');
      return;
    }

    try {
      setCreatingTicket(true);
      const payload = {
        external_id: `ADMIN-${Date.now()}`,
        people: Number(newTicket.people),
        longitude: Number(newTicket.longitude),
        latitude: Number(newTicket.latitude),
        text: newTicket.text,
        place: newTicket.place,
        category: newTicket.category,
      };
      await axios.post('/api/sos/', payload);
      toast.success('Ticket created successfully');
      setShowCreateModal(false);
      setNewTicket({
        people: 1,
        longitude: 78.4867,
        latitude: 17.385,
        text: '',
        place: '',
        category: 'General Emergency',
      });
      await fetchTickets();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create ticket');
    } finally {
      setCreatingTicket(false);
    }
  };

  const handleDeleteTicket = async (ticketId) => {
    if (!isAdmin) {
      toast.error('Only admins can delete tickets');
      return;
    }

    if (!window.confirm('Delete this ticket permanently?')) {
      return;
    }

    try {
      await axios.delete(`/api/sos/${ticketId}`);
      toast.success('Ticket deleted successfully');
      await fetchTickets();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to delete ticket');
    }
  };

  const getPriorityColor = (priority) => {
    const colors = {
      1: 'bg-gray-100 text-gray-700',
      2: 'bg-blue-100 text-blue-700',
      3: 'bg-yellow-100 text-yellow-700',
      4: 'bg-orange-100 text-orange-700',
      5: 'bg-red-100 text-red-700',
    };
    return colors[priority] || colors[1];
  };

  const getStatusColor = (status) => {
    const colors = {
      Pending: 'bg-yellow-100 text-yellow-800',
      'Pending Assignment': 'bg-orange-100 text-orange-800',
      'In Progress': 'bg-blue-100 text-blue-800',
      Done: 'bg-green-100 text-green-800',
      Cancelled: 'bg-gray-100 text-gray-800',
    };
    return colors[status] || colors.Pending;
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'Pending':
        return <Clock className="w-4 h-4" />;
      case 'Pending Assignment':
      case 'In Progress':
        return <AlertTriangle className="w-4 h-4" />;
      case 'Done':
        return <CheckCircle className="w-4 h-4" />;
      default:
        return <Clock className="w-4 h-4" />;
    }
  };

  const renderTicketRows = (items) => {
    if (items.length === 0) {
      return <div className="p-6 text-center text-gray-500">No tickets in this section.</div>;
    }

    return items.map((ticket) => {
      const assignedName = ticket.assigned_to ? staffLookup[ticket.assigned_to] || ticket.assigned_to : 'Unassigned';

      return (
        <div
          key={ticket.id}
          onClick={() => handleTicketClick(ticket)}
          className="p-6 hover:bg-gray-50 cursor-pointer transition-colors duration-200 border-t border-gray-100 first:border-t-0"
        >
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center space-x-3 mb-2">
                <span className={`px-3 py-1 rounded-full text-xs font-medium ${getPriorityColor(ticket.priority)}`}>
                  Priority {ticket.priority}
                </span>
                <span className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(ticket.status)} flex items-center space-x-1`}>
                  {getStatusIcon(ticket.status)}
                  <span>{ticket.status}</span>
                </span>
                <span className="text-sm text-gray-500">{formatTicketReportedAt(ticket)}</span>
              </div>

              <h4 className="text-lg font-semibold text-gray-900 mb-2">
                {ticket.category} - {ticket.place}
              </h4>

              <p className="text-gray-600 mb-3 line-clamp-2">{ticket.text}</p>

              <div className="flex items-center space-x-4 text-sm text-gray-500 flex-wrap">
                <div className="flex items-center space-x-1">
                  <Users className="w-4 h-4" />
                  <span>{ticket.people} people affected</span>
                </div>
                <div className="flex items-center space-x-1">
                  <MapPin className="w-4 h-4" />
                  <span>{Number(ticket.latitude).toFixed(4)}, {Number(ticket.longitude).toFixed(4)}</span>
                </div>
                <div className="flex items-center space-x-1">
                  <span>Assigned to: {assignedName}</span>
                </div>
                <div className="flex items-center space-x-2">
                  <div className="flex items-center space-x-1 text-green-600">
                    <Building className="w-3 h-3" />
                    <span className="text-xs">Shelter</span>
                  </div>
                  <div className="flex items-center space-x-1 text-red-600">
                    <Heart className="w-3 h-3" />
                    <span className="text-xs">Hospital</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="ml-4 flex items-center space-x-2">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  window.open(`https://www.google.com/maps/search/hospitals+near+${ticket.latitude},${ticket.longitude}`, '_blank');
                }}
                className="p-2 text-red-400 hover:text-red-600 rounded-lg hover:bg-red-50"
                title="Find nearby hospitals"
              >
                <Heart className="w-4 h-4" />
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  window.open(`https://www.google.com/maps/search/shelters+near+${ticket.latitude},${ticket.longitude}`, '_blank');
                }}
                className="p-2 text-green-400 hover:text-green-600 rounded-lg hover:bg-green-50"
                title="Find nearby shelters"
              >
                <Building className="w-4 h-4" />
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleTicketClick(ticket);
                }}
                className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100"
                disabled={!canEdit}
                title={canEdit ? 'Edit ticket' : 'Read-only access'}
              >
                <Edit className="w-4 h-4" />
              </button>
              {isAdmin && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteTicket(ticket.id);
                  }}
                  className="p-2 text-red-400 hover:text-red-600 rounded-lg hover:bg-red-50"
                  title="Delete ticket"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  window.open(`https://www.google.com/maps/dir/?api=1&destination=${ticket.latitude},${ticket.longitude}`, '_blank');
                }}
                className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100"
              >
                <Navigation className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      );
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="spinner"></div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">SOS Tickets</h1>
          <p className="text-gray-600">Manage emergency response requests</p>
        </div>
        <div className="flex items-center space-x-3">
          {isAdmin && (
            <button
              onClick={() => setShowCreateModal(true)}
              className="inline-flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              <Plus className="w-4 h-4" />
              <span>Create Ticket</span>
            </button>
          )}
          <div className="text-sm text-gray-500">
            Total: {tickets.length} | New: {tickets.filter((t) => NEW_TICKET_STATUSES.includes(t.status)).length} | Ongoing:{' '}
            {tickets.filter((t) => ONGOING_TICKET_STATUSES.includes(t.status)).length} | Served:{' '}
            {tickets.filter((t) => SERVED_TICKET_STATUSES.includes(t.status)).length}
          </div>
        </div>
      </div>

      <div className="bg-gradient-to-r from-blue-50 to-green-50 p-4 rounded-xl border border-blue-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-6">
            <div className="flex items-center space-x-2">
              <Building className="w-5 h-5 text-green-600" />
              <span className="text-sm font-medium text-green-800">Shelters Available</span>
            </div>
            <div className="flex items-center space-x-2">
              <Heart className="w-5 h-5 text-red-600" />
              <span className="text-sm font-medium text-red-800">Hospitals Available</span>
            </div>
            <div className="flex items-center space-x-2">
              <Navigation className="w-5 h-5 text-blue-600" />
              <span className="text-sm font-medium text-blue-800">Quick Navigation</span>
            </div>
          </div>
          <div className="text-xs text-blue-600">Click facility icons for quick Google Maps access</div>
        </div>
      </div>

      <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-4">
          <div className="lg:col-span-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search tickets..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>

          <div>
            <select
              value={filters.status}
              onChange={(e) => setFilters({ ...filters, status: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="">All Status</option>
              <option value="Pending">Pending</option>
              <option value="Pending Assignment">Pending Assignment</option>
              <option value="In Progress">In Progress</option>
              <option value="Done">Done</option>
              <option value="Cancelled">Cancelled</option>
            </select>
          </div>

          <div>
            <select
              value={filters.category}
              onChange={(e) => setFilters({ ...filters, category: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="">All Categories</option>
              {categories.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </div>

          <div>
            <select
              value={filters.priority}
              onChange={(e) => setFilters({ ...filters, priority: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="">All Priorities</option>
              <option value="1">Priority 1</option>
              <option value="2">Priority 2</option>
              <option value="3">Priority 3</option>
              <option value="4">Priority 4</option>
              <option value="5">Priority 5</option>
            </select>
          </div>

          <div>
            <select
              value={filters.region}
              onChange={(e) => setFilters({ ...filters, region: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="">All Regions</option>
              {regions.map((region) => (
                <option key={region.value} value={region.value}>
                  {region.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {filteredTickets.length === 0 ? (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 text-center text-gray-500">
          No tickets found matching the current filters.
        </div>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200">
          <div className="p-6 border-b border-gray-200 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <h3 className="text-lg font-semibold text-gray-900">Ticket Lifecycle</h3>
            <div className="inline-flex rounded-lg border border-gray-200 overflow-hidden">
              {LIFECYCLE_FILTERS.map((item) => {
                const count = lifecycleBuckets[item.id]?.length || 0;
                const isActive = activeLifecycle === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => setActiveLifecycle(item.id)}
                    className={`px-4 py-2 text-sm font-medium border-r border-gray-200 last:border-r-0 transition-colors ${
                      isActive ? 'bg-blue-600 text-white' : 'bg-white text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    {item.label} ({count})
                  </button>
                );
              })}
            </div>
          </div>

          <div className="p-4 border-b border-gray-100 flex items-center justify-between">
            <span className="text-sm text-gray-700 font-medium">{activeLifecycleConfig.label}</span>
            <span className={`text-xs px-3 py-1 rounded-full ${activeLifecycleConfig.badge}`}>{visibleTickets.length}</span>
          </div>

          {renderTicketRows(visibleTickets)}
        </div>
      )}

      {showCreateModal && isAdmin && (
        <div className="fixed inset-0 bg-black/40 z-40 flex items-center justify-center p-4">
          <div className="w-full max-w-xl bg-white rounded-xl shadow-xl p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-xl font-semibold text-gray-900">Create Ticket</h3>
              <button onClick={() => setShowCreateModal(false)} className="text-gray-500 hover:text-gray-700">
                x
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="md:col-span-2">
                <label className="block text-sm text-gray-700 mb-1">Description</label>
                <textarea
                  rows={3}
                  value={newTicket.text}
                  onChange={(e) => setNewTicket({ ...newTicket, text: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  placeholder="Describe the incident"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-700 mb-1">Place</label>
                <input
                  type="text"
                  value={newTicket.place}
                  onChange={(e) => setNewTicket({ ...newTicket, place: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  placeholder="Location name"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-700 mb-1">Category</label>
                <input
                  type="text"
                  value={newTicket.category}
                  onChange={(e) => setNewTicket({ ...newTicket, category: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  placeholder="Flood Rescue / Medical Emergency"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-700 mb-1">People</label>
                <input
                  type="number"
                  min="1"
                  value={newTicket.people}
                  onChange={(e) => setNewTicket({ ...newTicket, people: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-700 mb-1">Latitude</label>
                <input
                  type="number"
                  step="0.0001"
                  value={newTicket.latitude}
                  onChange={(e) => setNewTicket({ ...newTicket, latitude: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-700 mb-1">Longitude</label>
                <input
                  type="number"
                  step="0.0001"
                  value={newTicket.longitude}
                  onChange={(e) => setNewTicket({ ...newTicket, longitude: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
              </div>
            </div>

            <div className="flex items-center justify-end space-x-3 pt-2">
              <button
                onClick={() => setShowCreateModal(false)}
                className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateTicket}
                disabled={creatingTicket}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {creatingTicket ? 'Creating...' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showModal && selectedTicket && (
        <TicketModal
          ticket={selectedTicket}
          isOpen={showModal}
          onClose={() => setShowModal(false)}
          onStatusUpdate={handleStatusUpdate}
          canEdit={canEdit}
        />
      )}
    </div>
  );
};

export default Tickets;
