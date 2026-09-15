/**
 * JOBPOST AGGREGATOR - Client-side Interactive JavaScript
 * Pure Vanilla JavaScript (No React, No Frameworks)
 */

document.addEventListener('DOMContentLoaded', () => {
  initMobileNav();
  initBookmarks();
  initApplicationTracker();
  initJobReportModal();
  initTabs();
  initAdminActions();
  initAutoDismissAlerts();
});

// Mobile Nav Toggle
function initMobileNav() {
  const toggle = document.querySelector('.mobile-toggle');
  const nav = document.querySelector('.main-nav');
  if (!toggle || !nav) return;

  toggle.addEventListener('click', () => {
    const isVisible = window.getComputedStyle(nav).display !== 'none';
    nav.style.display = isVisible ? 'none' : 'flex';
    if (!isVisible) {
      nav.style.flexDirection = 'column';
      nav.style.position = 'absolute';
      nav.style.top = '72px';
      nav.style.left = '0';
      nav.style.right = '0';
      nav.style.background = '#ffffff';
      nav.style.padding = '20px';
      nav.style.boxShadow = '0 10px 15px -3px rgba(0,0,0,0.1)';
      nav.style.borderBottom = '1px solid #e2e8f0';
    }
  });
}

// Bookmark / Save Job Handler
function initBookmarks() {
  document.querySelectorAll('.btn-bookmark').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      e.stopPropagation();
      const jobId = btn.getAttribute('data-job-id');
      if (!jobId) return;

      try {
        const res = await fetch(`/api/jobs/${jobId}/save`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        });
        const data = await res.json();
        if (res.status === 401) {
          window.location.href = '/login?next=' + encodeURIComponent(window.location.pathname);
          return;
        }
        if (data.saved) {
          btn.classList.add('saved');
          btn.title = 'Saved to Bookmarks';
          btn.innerHTML = '★';
          showToast('Job saved to your bookmarks!');
        } else {
          btn.classList.remove('saved');
          btn.title = 'Save Job';
          btn.innerHTML = '☆';
          showToast('Job removed from bookmarks');
        }
      } catch (err) {
        console.error('Save error:', err);
      }
    });
  });
}

// Application Tracker Modal & Submission
function initApplicationTracker() {
  const modal = document.getElementById('applyTrackModal');
  const trackBtns = document.querySelectorAll('.btn-track-application');
  if (!modal) return;

  const closeBtn = modal.querySelector('.modal-close-btn');
  const cancelBtn = modal.querySelector('.btn-cancel-modal');
  const form = document.getElementById('trackApplicationForm');

  trackBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const jobId = btn.getAttribute('data-job-id');
      const jobTitle = btn.getAttribute('data-job-title');
      const currentStatus = btn.getAttribute('data-current-status') || 'Applied';
      const currentNotes = btn.getAttribute('data-current-notes') || '';

      document.getElementById('trackJobId').value = jobId;
      document.getElementById('trackJobTitleDisplay').textContent = jobTitle;
      document.getElementById('trackStatusSelect').value = currentStatus;
      document.getElementById('trackNotesTextarea').value = currentNotes;
      
      modal.classList.add('open');
    });
  });

  const closeModal = () => modal.classList.remove('open');
  if (closeBtn) closeBtn.addEventListener('click', closeModal);
  if (cancelBtn) cancelBtn.addEventListener('click', closeModal);

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const jobId = document.getElementById('trackJobId').value;
      const status = document.getElementById('trackStatusSelect').value;
      const notes = document.getElementById('trackNotesTextarea').value;

      try {
        const res = await fetch(`/api/jobs/${jobId}/track`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status, notes })
        });
        const data = await res.json();
        if (data.success) {
          showToast('Application tracking status updated!');
          closeModal();
          setTimeout(() => window.location.reload(), 600);
        } else {
          alert(data.error || 'Failed to update tracking');
        }
      } catch (err) {
        alert('Network error updating application tracker');
      }
    });
  }
}

// Job Report Modal
function initJobReportModal() {
  const modal = document.getElementById('reportJobModal');
  const reportBtns = document.querySelectorAll('.btn-report-job');
  if (!modal) return;

  const closeBtn = modal.querySelector('.modal-close-btn');
  const cancelBtn = modal.querySelector('.btn-cancel-modal');
  const form = document.getElementById('reportJobForm');

  reportBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const jobId = btn.getAttribute('data-job-id');
      const jobTitle = btn.getAttribute('data-job-title');
      document.getElementById('reportJobId').value = jobId;
      document.getElementById('reportJobTitleDisplay').textContent = jobTitle;
      modal.classList.add('open');
    });
  });

  const closeModal = () => modal.classList.remove('open');
  if (closeBtn) closeBtn.addEventListener('click', closeModal);
  if (cancelBtn) cancelBtn.addEventListener('click', closeModal);

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const jobId = document.getElementById('reportJobId').value;
      const reason = document.getElementById('reportReasonSelect').value;
      const details = document.getElementById('reportDetailsTextarea').value;

      try {
        const res = await fetch(`/api/jobs/${jobId}/report`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reason, details })
        });
        const data = await res.json();
        if (data.success) {
          showToast('Report submitted. Our admin team will investigate.');
          closeModal();
        } else {
          alert(data.error || 'Failed to submit report');
        }
      } catch (err) {
        alert('Error submitting report');
      }
    });
  }
}

// Tab Switching
function initTabs() {
  const tabButtons = document.querySelectorAll('.dashboard-tab');
  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-tab-target');
      if (!targetId) return;

      // Deactivate all in same container
      const container = btn.closest('.tabs-container') || document;
      container.querySelectorAll('.dashboard-tab').forEach(b => b.classList.remove('active'));
      container.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      const targetPane = document.getElementById(targetId);
      if (targetPane) targetPane.classList.add('active');
    });
  });
}

// Admin Operations (Sync Sources, Remove Duplicates, Delete Jobs)
function initAdminActions() {
  // 1. Sync Job Sources Now
  const syncBtn = document.getElementById('btnSyncAllSources');
  if (syncBtn) {
    syncBtn.addEventListener('click', async () => {
      syncBtn.disabled = true;
      syncBtn.innerHTML = '⟳ Synchronizing Feeds...';
      try {
        const res = await fetch('/api/admin/sync-sources', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          showToast(`Sync complete! Added: ${data.new_jobs}, Duplicates flagged: ${data.duplicates}`);
          setTimeout(() => window.location.reload(), 1200);
        } else {
          alert(data.error || 'Sync failed');
          syncBtn.disabled = false;
          syncBtn.innerHTML = '⟳ Sync Sources Now';
        }
      } catch (err) {
        alert('Network error running source sync');
        syncBtn.disabled = false;
        syncBtn.innerHTML = '⟳ Sync Sources Now';
      }
    });
  }

  // 2. Remove Duplicate Job Action
  document.querySelectorAll('.btn-remove-duplicate').forEach(btn => {
    btn.addEventListener('click', async () => {
      if (!confirm('Are you sure you want to remove this duplicate job posting?')) return;
      const jobId = btn.getAttribute('data-job-id');
      try {
        const res = await fetch(`/api/admin/jobs/${jobId}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
          showToast('Duplicate job post removed successfully');
          const row = btn.closest('tr');
          if (row) row.remove();
        }
      } catch (err) {
        alert('Error removing duplicate job');
      }
    });
  });

  // 3. Mark / Clean Expired Jobs
  const cleanExpiredBtn = document.getElementById('btnCleanExpiredJobs');
  if (cleanExpiredBtn) {
    cleanExpiredBtn.addEventListener('click', async () => {
      if (!confirm('Mark all jobs past deadline as EXPIRED?')) return;
      try {
        const res = await fetch('/api/admin/clean-expired', { method: 'POST' });
        const data = await res.json();
        showToast(`Scan complete: ${data.expired_count} jobs marked as Expired.`);
        setTimeout(() => window.location.reload(), 1000);
      } catch (err) {
        alert('Error checking expired jobs');
      }
    });
  }
}

// Toast notification helper
function showToast(message) {
  let toast = document.getElementById('floatingToast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'floatingToast';
    toast.style.position = 'fixed';
    toast.style.bottom = '24px';
    toast.style.right = '24px';
    toast.style.background = '#0f172a';
    toast.style.color = '#ffffff';
    toast.style.padding = '12px 20px';
    toast.style.borderRadius = '8px';
    toast.style.boxShadow = '0 10px 15px -3px rgba(0,0,0,0.2)';
    toast.style.fontSize = '14px';
    toast.style.fontWeight = '500';
    toast.style.zIndex = '9999';
    toast.style.transition = 'all 0.3s ease';
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.style.opacity = '1';
  toast.style.transform = 'translateY(0)';

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
  }, 3000);
}

// Auto dismiss flash messages after 4 seconds
function initAutoDismissAlerts() {
  setTimeout(() => {
    document.querySelectorAll('.alert-message').forEach(alert => {
      alert.style.transition = 'opacity 0.5s ease';
      alert.style.opacity = '0';
      setTimeout(() => alert.remove(), 500);
    });
  }, 4000);
}
