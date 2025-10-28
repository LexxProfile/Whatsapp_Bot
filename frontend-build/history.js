document.addEventListener('DOMContentLoaded', function() {
    const historyList = document.getElementById('historyList');
    // Membuat URL API dinamis. Ini akan berfungsi di localhost dan saat diakses dari luar.
    const API_BASE_URL = `${window.location.protocol}//${window.location.hostname}:8000`;
    
    // Ambil token dari localStorage
    const token = localStorage.getItem('authToken');
    
    // Fungsi untuk memformat tanggal agar lebih mudah dibaca
    function formatDateTime(isoString) {
        if (!isoString) return 'Waktu tidak tersedia';
        try {
            const date = new Date(isoString);
            return date.toLocaleString('id-ID', { dateStyle: 'long', timeStyle: 'short' });
        } catch (e) {
            return isoString; // Kembalikan string asli jika format tidak valid
        }
    }

    // Fungsi untuk mengambil dan menampilkan riwayat
    async function fetchAndDisplayHistory() {
        if (!token) {
            historyList.innerHTML = `
                <li class="liquid-glass rounded-xl p-6 text-center text-gray-700">
                    <i class="fas fa-exclamation-triangle text-xl mb-3"></i>
                    <p class="font-bold">Anda harus login untuk melihat riwayat chat.</p>
                    <a href="login.html" class="mt-4 inline-block bg-blue-500 text-white font-bold py-2 px-4 rounded-lg hover:bg-blue-600 transition-colors">
                        Login Sekarang
                    </a>
                </li>`;
            // Hentikan polling jika user tidak login
            if (window.historyInterval) clearInterval(window.historyInterval);
            return;
        }

        try {
            const response = await fetch(`${API_BASE_URL}/api/chat-history`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                // Jika token tidak valid (misal: expired), hentikan polling
                if (response.status === 401) clearInterval(window.historyInterval);
                const errorData = await response.json();
                throw new Error(errorData.detail || `Gagal memuat data (Status: ${response.status})`);
            }

            const chatHistory = await response.json();
            historyList.innerHTML = ''; // Kosongkan list

            if (chatHistory.length === 0) {
                historyList.innerHTML = `<li class="liquid-glass rounded-xl p-4 text-center text-gray-600">Tidak ada riwayat chat yang ditemukan.</li>`;
                return;
            }

            // Tampilkan setiap riwayat chat dalam daftar
            chatHistory.forEach(chat => {
                const listItem = document.createElement('li');
                listItem.className = 'liquid-glass rounded-xl p-4 flex justify-between items-center'; // Kelas untuk <li>

                // Hapus atribut onclick dari HTML untuk keamanan dan keandalan
                listItem.innerHTML = `
                    <div class="flex-grow cursor-pointer detail-trigger">
                        <p class="font-bold text-gray-800">ID: ${chat.id} - <span class="text-blue-600">${chat.user_message || 'N/A'}</span></p>
                        <p class="text-sm text-gray-600 mt-1">${formatDateTime(chat.waktu)}</p>
                    </div>
                    <div class="flex items-center space-x-2 ml-4">
                        <button class="liquid-glass-hover rounded-lg p-3 text-gray-700 detail-trigger" title="Lihat Detail">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="liquid-glass-hover rounded-lg p-3 text-orange-500 order-trigger" title="Tambah ke Orderan">
                            <i class="fas fa-cart-plus"></i>
                        </button>
                    </div>
                `;
                historyList.appendChild(listItem);

                // Tambahkan event listener ke semua elemen pemicu di dalam listItem
                listItem.querySelectorAll('.detail-trigger').forEach(trigger => {
                    trigger.addEventListener('click', () => showChatDetail(formatDateTime(chat.waktu), chat.user_message, chat.bot_response));
                });
                listItem.querySelector('.order-trigger').addEventListener('click', () => showAddOrderModal(chat.user_message));
            });

        } catch (error) {
            console.error('Fetch History Error:', error);
            // Hanya tampilkan error jika list masih kosong, agar tidak mengganggu pengguna
            if (historyList.children.length <= 1) {
                historyList.innerHTML = `<li class="liquid-glass rounded-xl p-4 text-center text-red-600">${error.message}. Mungkin sesi Anda telah berakhir, silakan <a href="login.html" class="font-bold underline">login kembali</a>.</li>`;
            }
        }
    }

    // Panggil fungsi pertama kali saat halaman dimuat
    fetchAndDisplayHistory();

    // Atur interval untuk memanggil fungsi setiap 10 detik (10000 milidetik)
    window.historyInterval = setInterval(fetchAndDisplayHistory, 10000);

    // --- Event Listener untuk Form Tambah Orderan ---
    const addOrderForm = document.getElementById('addOrderForm');
    if (addOrderForm) {
        addOrderForm.addEventListener('submit', async function(event) {
            event.preventDefault();

            const itemName = document.getElementById('orderItemName').textContent;
            const quantity = document.getElementById('orderQuantity').value;
            const errorEl = document.getElementById('orderError');
            const successEl = document.getElementById('orderSuccess');

            errorEl.classList.add('hidden');
            successEl.classList.add('hidden');

            try {
                const response = await fetch(`${API_BASE_URL}/api/orders`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify({
                        item_name: itemName,
                        quantity: parseInt(quantity)
                    })
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || 'Gagal menambahkan order.');
                }

                // Pesan sukses yang lebih baik dengan link ke halaman orderan
                successEl.innerHTML = `Order berhasil ditambahkan! <a href="orderan.html" class="font-bold underline hover:text-green-700">Lihat Daftar Orderan</a>`;
                successEl.classList.remove('hidden');

                // Kosongkan form setelah sukses
                addOrderForm.reset();

                // Tutup modal setelah 2 detik
                setTimeout(() => {
                    closeAddOrderModal();
                }, 2000);

            } catch (error) {
                errorEl.textContent = error.message;
                errorEl.classList.remove('hidden');
            }
        });
    }
});