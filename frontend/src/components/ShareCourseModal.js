import React, { useState, useEffect, useCallback } from 'react';
import Modal from './Modal';
import { shareCourse, getCourseShares, revokeCourseShare } from '../services/course';
import LoadingSpinner from './LoadingSpinner';

export default function ShareCourseModal({ open, onClose, courseId, courseName, isOwner, onShareUpdate }) {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [sharedUsers, setSharedUsers] = useState([]);
  const [loadingShares, setLoadingShares] = useState(false);

  const loadSharedUsers = useCallback(async () => {
    if (!courseId) return;
    try {
      setLoadingShares(true);
      const shares = await getCourseShares(courseId);
      setSharedUsers(shares);
    } catch (err) {
      console.error('Failed to load shared users:', err);
    } finally {
      setLoadingShares(false);
    }
  }, [courseId]);

  useEffect(() => {
    if (open && courseId && isOwner) {
      loadSharedUsers();
    }
    // Reset state when modal closes
    if (!open) {
      setEmail('');
      setError('');
      setSuccess('');
    }
  }, [open, courseId, isOwner, loadSharedUsers]);

  const handleShare = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (!email.trim()) {
      setError('Please enter an email address');
      return;
    }

    // Basic email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      setError('Please enter a valid email address');
      return;
    }

    try {
      setLoading(true);
      await shareCourse(courseId, email.trim());
      setSuccess(`Course shared successfully with ${email}`);
      setEmail('');
      
      // Reload shared users list
      await loadSharedUsers();
      
      // Notify parent to refresh course list (to update badge)
      if (onShareUpdate) {
        onShareUpdate();
      }
      
      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      const errorMessage = err.response?.data?.detail || 'Failed to share course';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleRevoke = async (userId, userEmail) => {
    if (!window.confirm(`Are you sure you want to revoke access for ${userEmail}?`)) {
      return;
    }

    try {
      await revokeCourseShare(courseId, userId);
      setSuccess(`Access revoked for ${userEmail}`);
      await loadSharedUsers();
      
      // Notify parent to refresh course list (to update badge)
      if (onShareUpdate) {
        onShareUpdate();
      }
      
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError('Failed to revoke access');
    }
  };

  const formatDate = (isoDate) => {
    try {
      const date = new Date(isoDate);
      return date.toLocaleDateString('en-US', { 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric' 
      });
    } catch {
      return isoDate;
    }
  };

  // Don't render if no course is selected
  if (!courseId || !courseName) return null;

  return (
    <Modal open={open} onClose={onClose}>
      <div style={{ minWidth: 500, position: 'relative' }}>
        {/* Close Button */}
        <button
          onClick={onClose}
          style={{
            position: 'absolute',
            top: -8,
            right: -8,
            background: '#f1f5f9',
            border: 'none',
            borderRadius: '50%',
            width: 32,
            height: 32,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            fontSize: 18,
            color: '#64748b',
            transition: 'all 0.2s'
          }}
          onMouseEnter={(e) => {
            e.target.style.background = '#e2e8f0';
            e.target.style.color = '#1e293b';
          }}
          onMouseLeave={(e) => {
            e.target.style.background = '#f1f5f9';
            e.target.style.color = '#64748b';
          }}
        >
          ×
        </button>

        {/* Modal Title */}
        <h2 style={{ 
          margin: '0 0 24px 0', 
          fontSize: 24, 
          fontWeight: 700, 
          color: '#1e293b',
          textAlign: 'center'
        }}>
          Share "{courseName}"
        </h2>
        {/* Share Form */}
        {isOwner && (
          <form onSubmit={handleShare} style={{ marginBottom: 24 }}>
            <label style={{ display: 'block', marginBottom: 8, fontWeight: 600, fontSize: 14 }}>
              Share with user (by email)
            </label>
            <div style={{ display: 'flex', gap: 10 }}>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="user@example.com"
                style={{
                  flex: 1,
                  padding: '10px 14px',
                  border: '1.5px solid #e0e7ef',
                  borderRadius: 8,
                  fontSize: 14,
                  outline: 'none',
                  transition: 'border-color 0.2s'
                }}
                onFocus={(e) => e.target.style.borderColor = '#2563eb'}
                onBlur={(e) => e.target.style.borderColor = '#e0e7ef'}
                disabled={loading}
              />
              <button
                type="submit"
                disabled={loading}
                style={{
                  padding: '10px 24px',
                  background: loading ? '#94a3b8' : '#2563eb',
                  color: 'white',
                  border: 'none',
                  borderRadius: 8,
                  fontWeight: 600,
                  fontSize: 14,
                  cursor: loading ? 'not-allowed' : 'pointer',
                  transition: 'background 0.2s'
                }}
                onMouseEnter={(e) => !loading && (e.target.style.background = '#1d4ed8')}
                onMouseLeave={(e) => !loading && (e.target.style.background = '#2563eb')}
              >
                {loading ? 'Sharing...' : 'Share'}
              </button>
            </div>

            {/* Error Message */}
            {error && (
              <div style={{
                marginTop: 12,
                padding: '10px 14px',
                background: '#fee2e2',
                border: '1px solid #fca5a5',
                borderRadius: 6,
                color: '#dc2626',
                fontSize: 14
              }}>
                {error}
              </div>
            )}

            {/* Success Message */}
            {success && (
              <div style={{
                marginTop: 12,
                padding: '10px 14px',
                background: '#d1fae5',
                border: '1px solid #6ee7b7',
                borderRadius: 6,
                color: '#059669',
                fontSize: 14
              }}>
                {success}
              </div>
            )}
          </form>
        )}

        {/* Shared Users List */}
        {isOwner && (
          <div>
            <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>
              Shared with ({sharedUsers.length})
            </h3>
            
            {loadingShares ? (
              <div style={{ display: 'flex', justifyContent: 'center', padding: 20 }}>
                <LoadingSpinner />
              </div>
            ) : sharedUsers.length === 0 ? (
              <p style={{ color: '#64748b', fontSize: 14, fontStyle: 'italic' }}>
                This course hasn't been shared with anyone yet.
              </p>
            ) : (
              <div style={{ maxHeight: 300, overflowY: 'auto' }}>
                {sharedUsers.map((share) => (
                  <div
                    key={share.user_id}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '12px 14px',
                      background: '#f8fafc',
                      border: '1px solid #e2e8f0',
                      borderRadius: 8,
                      marginBottom: 8
                    }}
                  >
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 2 }}>
                        {share.email}
                      </div>
                      <div style={{ fontSize: 12, color: '#64748b' }}>
                        Shared on {formatDate(share.shared_at)}
                      </div>
                    </div>
                    <button
                      onClick={() => handleRevoke(share.user_id, share.email)}
                      style={{
                        padding: '6px 14px',
                        background: 'transparent',
                        color: '#dc2626',
                        border: '1px solid #dc2626',
                        borderRadius: 6,
                        fontSize: 13,
                        fontWeight: 600,
                        cursor: 'pointer',
                        transition: 'all 0.2s'
                      }}
                      onMouseEnter={(e) => {
                        e.target.style.background = '#dc2626';
                        e.target.style.color = 'white';
                      }}
                      onMouseLeave={(e) => {
                        e.target.style.background = 'transparent';
                        e.target.style.color = '#dc2626';
                      }}
                    >
                      Revoke
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* View for non-owners (shared users) */}
        {!isOwner && (
          <div style={{ textAlign: 'center', padding: '20px 0' }}>
            <p style={{ color: '#64748b', fontSize: 14 }}>
              This course has been shared with you. You have full access to all course materials.
            </p>
          </div>
        )}
      </div>
    </Modal>
  );
}

