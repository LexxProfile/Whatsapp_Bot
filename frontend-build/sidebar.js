/* ======================
   JWT PARSER
====================== */
function parseJwt(token) {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch {
    return null;
  }
}

/* ======================
   GLOBALS
====================== */
window.toggleSidebar = function () {
  document.getElementById('sidebar')?.classList.toggle('show');
  document.getElementById('overlay')?.classList.toggle('show');
};

// URL API Backend Otomatis
window.API_BASE_URL = `${window.location.protocol}//${window.location.hostname}`;

/* ======================
   MAIN PROCESS
====================== */
document.addEventListener('DOMContentLoaded', async () => {

  /* --- 1. AUTH CHECK --- */
  const token = localStorage.getItem('authToken');
  if (!token && !location.pathname.includes('login.html')) {
    location.href = 'login.html';
    return;
  }

  // Ambil Nomor HP dari Token (Data real dari login)
  const decodedToken = parseJwt(token);
  const userPhone = decodedToken ? decodedToken.sub : 'Unknown';

  /* --- 2. LOAD SIDEBAR HTML --- */
  const sidebarContainer = document.getElementById('sidebar-container');
  if (sidebarContainer) {
    try {
      const res = await fetch('sidebar.html');
      if (res.ok) {
        sidebarContainer.innerHTML = await res.text();
      }
    } catch (err) {
      console.error("Gagal memuat sidebar.html:", err);
    }
  }

  /* --- 3. FETCH ROLE DARI DATABASE --- */
  let userRole = ''; 

  if (token) {
    try {
      const res = await fetch(`${window.API_BASE_URL}/api/user/profile`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (res.ok) {
        const data = await res.json();
        userRole = data.role.toLowerCase(); // Ambil role dari get_user_profile di main.py
      } else if (res.status === 401) {
        localStorage.removeItem('authToken');
        location.href = 'login.html';
        return;
      }
    } catch (err) {
      console.warn('Gagal fetch profil database.');
    }
  }

  /* --- 4. UPDATE UI (NO HP & ROLE) --- */
  const sidebarNameEl = document.getElementById('sidebarUserName');
  const roleLabels = document.querySelectorAll('.role b, #user-role-display');

  // Set Nomor HP ke Sidebar
  if (sidebarNameEl) sidebarNameEl.textContent = userPhone;
  
  // Set Text Role ke Sidebar
  roleLabels.forEach(el => {
    el.textContent = userRole.toUpperCase();
  });

  /* --- 5. ROLE ACCESS CONTROL (HAK AKSES) --- */
  const reportsLink = sidebarContainer?.querySelector('[data-page="reports"]');
  const usersLink   = sidebarContainer?.querySelector('[data-page="users"]');
  const sparepartLink = sidebarContainer?.querySelector('[data-page="sparepart"]');
  const estimationLink = sidebarContainer?.querySelector('[data-page="estimasi_jasa"]');
  const feedbackIntelligenceLink = sidebarContainer?.querySelector('[data-page="feedback_intelligence"]');

  if (sidebarContainer) {
    // Sembunyikan menu admin/sensitif secara default
    if (reportsLink) reportsLink.style.display = 'none';
    if (usersLink) usersLink.style.display = 'none';
    if (feedbackIntelligenceLink) feedbackIntelligenceLink.style.display = 'none';

    // --- PROTEKSI AKSES LANGSUNG KE FEEDBACK DASHBOARD ---
    const currentPage = window.location.pathname;
    if (currentPage.includes('feedbackdashboard.html')) {
      if (userRole !== 'owner') {
        alert("Anda tidak memiliki akses ke halaman ini.");
        window.location.href = 'index.html';
        return;
      }
    }

    // Pengaturan Hak Akses per Role
    if (userRole === 'owner') {
      // Owner: Akses Semua termasuk Feedback Intelligence
      if (reportsLink) reportsLink.style.display = 'flex';
      if (usersLink) usersLink.style.display = 'flex';
      if (feedbackIntelligenceLink) feedbackIntelligenceLink.style.display = 'flex';
    } else if (userRole === 'manager') {
      // Manager: Akses Reports dan User Management, tapi tidak Feedback Intelligence
      if (reportsLink) reportsLink.style.display = 'flex';
      if (usersLink) usersLink.style.display = 'flex';
    } 
    else if (userRole === 'sa') {
      // SA: Akses Estimasi Jasa & Reports (Tanpa User Management)
      if (reportsLink) reportsLink.style.display = 'flex';
      if (estimationLink) estimationLink.classList.remove('hidden');
    } 
    else if (userRole === 'sparepart') {
      // Sparepart: Hanya Sparepart Search
      if (estimationLink) estimationLink.style.display = 'none';
    }
  }

  /* --- 6. HIGHLIGHT ACTIVE MENU --- */
  const currentMenu = document.body.dataset.menu;
  if (currentMenu && sidebarContainer) {
    const activeLink = sidebarContainer.querySelector(`.menu a[data-page="${currentMenu}"]`);
    if (activeLink) activeLink.classList.add('active');
  }

  /* --- 7. LOGOUT --- */
  document.addEventListener('click', (e) => {
    if (e.target && (e.target.id === 'logoutBtn' || e.target.closest('#logoutBtn'))) {
      localStorage.removeItem('authToken');
      location.href = 'login.html';
    }
  });
});