document.addEventListener('DOMContentLoaded', async () => {
    const token = localStorage.getItem('authToken');
    const tableBody = document.getElementById('userTableBody');
    const userCount = document.getElementById('userCount');

    async function fetchUsers() {
        try {
            const res = await fetch(`${window.API_BASE_URL}/api/admin/users`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const users = await res.ok ? await res.json() : [];
            renderUsers(users);
        } catch (err) { console.error("Gagal ambil data user", err); }
    }

    function renderUsers(users) {
        userCount.textContent = users.length;
        tableBody.innerHTML = users.map(user => `
            <tr class="border-b hover:bg-gray-50 transition-colors">
                <td class="p-4 font-medium">${user.phone_number}</td>
                <td class="p-4">
                    <select onchange="updateUser(${user.id}, this.value, '${user.status}')" 
                            class="bg-white border rounded px-2 py-1 text-sm focus:ring-2 focus:ring-blue-500">
                        <option value="owner" ${user.role === 'owner' ? 'selected' : ''}>OWNER</option>
                        <option value="manager" ${user.role === 'manager' ? 'selected' : ''}>MANAGER</option>
                        <option value="sa" ${user.role === 'sa' ? 'selected' : ''}>SA</option>
                        <option value="sparepart" ${user.role === 'sparepart' ? 'selected' : ''}>SPAREPART</option>
                        <option value="staff" ${user.role === 'staff' ? 'selected' : ''}>STAFF</option>
                    </select>
                </td>
                <td class="p-4">
                    <span class="px-2 py-1 rounded-full text-xs font-bold ${user.status === 'approved' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}">
                        ${user.status.toUpperCase()}
                    </span>
                </td>
                <td class="p-4">
                    <button onclick="deleteUser(${user.id})" class="text-red-500 hover:text-red-700 transition-colors">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </td>
            </tr>
        `).join('');
    }

    window.updateUser = async (id, newRole, currentStatus) => {
        if(!confirm("Ubah role user ini?")) return;
        try {
            await fetch(`${window.API_BASE_URL}/api/admin/users/${id}`, {
                method: 'PUT',
                headers: { 
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json' 
                },
                body: JSON.stringify({ role: newRole, status: currentStatus })
            });
            alert("Role berhasil diperbarui!");
        } catch (err) { alert("Gagal update"); }
    };

    window.deleteUser = async (id) => {
        if(!confirm("Hapus user ini secara permanen?")) return;
        try {
            await fetch(`${window.API_BASE_URL}/api/admin/users/${id}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            fetchUsers(); // Refresh data
        } catch (err) { alert("Gagal hapus"); }
    };

    fetchUsers();
});