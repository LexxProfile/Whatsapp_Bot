document.addEventListener('DOMContentLoaded', function() {
    const orderList = document.getElementById('orderList');
    // Membuat URL API dinamis. Ini akan berfungsi di localhost dan saat diakses dari luar.
    const API_BASE_URL = `${window.location.protocol}//${window.location.hostname}:8000`;
    
    // Ambil token dari localStorage
    const token = localStorage.getItem('authToken');

    // Fungsi untuk memformat tanggal
    function formatDateTime(isoString) {
        if (!isoString) return 'Waktu tidak tersedia';
        try {
            const date = new Date(isoString);
            return date.toLocaleString('id-ID', { dateStyle: 'long', timeStyle: 'short' });
        } catch (e) {
            return isoString;
        }
    }

    // Fungsi untuk mengambil dan menampilkan orderan
    async function fetchAndDisplayOrders() {
        if (!token) {
            orderList.innerHTML = `
                <li class="liquid-glass rounded-xl p-6 text-center text-gray-700">
                    <i class="fas fa-exclamation-triangle text-xl mb-3"></i>
                    <p class="font-bold">Anda harus login untuk melihat daftar orderan.</p>
                    <a href="login.html" class="mt-4 inline-block bg-blue-500 text-white font-bold py-2 px-4 rounded-lg hover:bg-blue-600 transition-colors">
                        Login Sekarang
                    </a>
                </li>`;
            if (window.orderInterval) clearInterval(window.orderInterval);
            return;
        }

        try {
            // [FIXED] Mengarahkan ke endpoint yang benar (/api/orders/list) untuk mengambil daftar orderan
            const response = await fetch(`${API_BASE_URL}/api/orders/list`, {
                method: 'GET',
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!response.ok) {
                if (response.status === 401) clearInterval(window.orderInterval);
                const errorData = await response.json();
                throw new Error(errorData.detail || `Gagal memuat data (Status: ${response.status})`);
            }

            const orders = await response.json();
            orderList.innerHTML = ''; // Kosongkan list

            if (orders.length === 0) {
                orderList.innerHTML = `<li class="liquid-glass rounded-xl p-4 text-center text-gray-300">Tidak ada orderan yang ditemukan.</li>`;
                return;
            }

            // Tampilkan setiap orderan dalam daftar
            orders.forEach(order => {
                const listItem = document.createElement('li');
                listItem.className = 'liquid-glass liquid-glass-hover rounded-xl p-4 cursor-pointer flex justify-between items-center';
                
                // Menambahkan properti timestamp yang diformat untuk modal
                const formattedOrder = { ...order, timestamp: formatDateTime(order.waktu) };

                listItem.innerHTML = `
                    <div class="text-white">
                        <p class="font-bold text-gray-100">${order.customer_name || 'Tanpa Nama'} - ID: ${order.id}</p>
                        <p class="text-sm text-gray-300">${formattedOrder.timestamp}</p>
                    </div>
                    <span class="text-sm font-semibold text-yellow-300">${order.status || 'Baru'}</span>
                `;
                listItem.onclick = () => showOrderDetail(formattedOrder);
                orderList.appendChild(listItem);
            });

        } catch (error) {
            console.error('Fetch Orders Error:', error);
            if (orderList.children.length <= 1) {
                orderList.innerHTML = `<li class="liquid-glass rounded-xl p-4 text-center text-red-600">${error.message}. Mungkin sesi Anda telah berakhir, silakan <a href="login.html" class="font-bold underline">login kembali</a>.</li>`;
            }
        }
    }

    // Panggil fungsi pertama kali
    fetchAndDisplayOrders();

    // Atur interval untuk memanggil fungsi setiap 15 detik (15000 milidetik)
    window.orderInterval = setInterval(fetchAndDisplayOrders, 15000);
});