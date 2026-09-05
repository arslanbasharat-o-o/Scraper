document.addEventListener('DOMContentLoaded', () => {
  const tbody = document.getElementById('usersTbody');
  const modal = document.getElementById('userModal');
  const modalCard = modal?.querySelector('[role="dialog"]');
  const form = document.getElementById('userForm');
  const addBtn = document.getElementById('addBtn');
  const cancelBtn = document.getElementById('cancelBtn');
  const modalTitle = document.getElementById('modalTitle');
  const pwdHint = document.getElementById('pwdHint');
  let modalReturnFocus = null;

  const focusableSelector = [
    'a[href]',
    'button:not([disabled])',
    'input:not([disabled]):not([type="hidden"])',
    'select:not([disabled])',
    'textarea:not([disabled])',
    '[tabindex]:not([tabindex="-1"])'
  ].join(',');

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function renderTableMessage(message) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;">${escapeHtml(message)}</td></tr>`;
  }

  function getModalFocusableElements() {
    if (!modalCard) return [];
    return Array.from(modalCard.querySelectorAll(focusableSelector)).filter(element => {
      const style = window.getComputedStyle(element);
      return style.display !== 'none' && style.visibility !== 'hidden';
    });
  }

  function openUserModal(opener) {
    modalReturnFocus = opener || document.activeElement;
    modal.classList.add('active');
    modal.setAttribute('aria-hidden', 'false');
    const firstInput = document.getElementById('username');
    window.requestAnimationFrame(() => {
      (firstInput || getModalFocusableElements()[0] || modalCard)?.focus();
    });
  }

  function closeUserModal() {
    modal.classList.remove('active');
    modal.setAttribute('aria-hidden', 'true');
    if (modalReturnFocus && typeof modalReturnFocus.focus === 'function' && document.contains(modalReturnFocus)) {
      modalReturnFocus.focus();
    }
    modalReturnFocus = null;
  }

  function fetchUsers() {
    renderTableMessage('Loading users...');
    fetch('/api/users')
      .then(res => {
        if (!res.ok) throw new Error(`Unable to load users (${res.status})`);
        return res.json();
      })
      .then(users => {
        tbody.innerHTML = '';
        if (!Array.isArray(users) || users.length === 0) {
          renderTableMessage('No users found.');
          return;
        }
        users.forEach(u => {
          const tr = document.createElement('tr');

          const actions = `
            <div class="user-actions">
              <button class="btn-export edit-btn" type="button" data-id="${escapeHtml(u.id)}">Edit</button>
              <button class="btn-danger-sm del-btn" type="button" data-id="${escapeHtml(u.id)}">Delete</button>
            </div>
          `;

          tr.innerHTML = `
            <td>${escapeHtml(u.id)}</td>
            <td><strong>${escapeHtml(u.username)}</strong></td>
            <td><span class="badge ${escapeHtml(u.role)}">${escapeHtml(u.role)}</span></td>
            <td>${escapeHtml(u.created_at || '')}</td>
            <td>${actions}</td>
          `;
          tbody.appendChild(tr);
        });
      })
      .catch(err => {
        console.error(err);
        renderTableMessage(err.message || 'Unable to load users.');
      });
  }

  fetchUsers();

  addBtn.addEventListener('click', () => {
    form.reset();
    document.getElementById('userId').value = '';
    document.getElementById('username').readOnly = false;
    modalTitle.textContent = 'Add User';
    pwdHint.style.display = 'none';
    document.getElementById('password').required = true;
    openUserModal(addBtn);
  });

  cancelBtn.addEventListener('click', () => {
    closeUserModal();
  });

  modal.addEventListener('click', e => {
    if (e.target === modal) closeUserModal();
  });

  document.addEventListener('keydown', e => {
    if (!modal.classList.contains('active')) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      closeUserModal();
      return;
    }
    if (e.key !== 'Tab') return;
    const focusable = getModalFocusableElements();
    if (!focusable.length) {
      e.preventDefault();
      modalCard?.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  });

  tbody.addEventListener('click', e => {
    if (e.target.classList.contains('edit-btn')) {
      const id = e.target.getAttribute('data-id');
      const tr = e.target.closest('tr');
      const username = tr.cells[1].textContent.trim();
      const role = tr.cells[2].textContent.trim();

      form.reset();
      document.getElementById('userId').value = id;
      document.getElementById('username').value = username;
      document.getElementById('username').readOnly = true; // prevent changing username for now
      document.getElementById('role').value = role;

      modalTitle.textContent = 'Edit User';
      pwdHint.style.display = 'inline';
      document.getElementById('password').required = false;

      openUserModal(e.target);
    }

    if (e.target.classList.contains('del-btn')) {
      const id = e.target.getAttribute('data-id');
      if (confirm('Are you sure you want to delete this user?')) {
        fetch(`/api/users/${id}`, { method: 'DELETE' })
          .then(res => res.json())
          .then(data => {
            if (data.error) alert(data.error);
            else fetchUsers();
          })
          .catch(err => alert(err.message || 'Failed to delete user.'));
      }
    }
  });

  form.addEventListener('submit', e => {
    e.preventDefault();
    const id = document.getElementById('userId').value;
    const data = {
      username: document.getElementById('username').value,
      password: document.getElementById('password').value,
      role: document.getElementById('role').value
    };

    if (id) {
      // Update
      fetch(`/api/users/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      })
      .then(res => res.json())
      .then(resData => {
        if (resData.error) alert(resData.error);
        else {
          closeUserModal();
          fetchUsers();
        }
      })
      .catch(err => alert(err.message || 'Failed to update user.'));
    } else {
      // Create
      fetch('/api/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      })
      .then(res => res.json())
      .then(resData => {
        if (resData.error) alert(resData.error);
        else {
          closeUserModal();
          fetchUsers();
        }
      })
      .catch(err => alert(err.message || 'Failed to create user.'));
    }
  });
});
