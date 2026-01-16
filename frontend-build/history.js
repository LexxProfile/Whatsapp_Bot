document.addEventListener('DOMContentLoaded', function() {
    const historyList = document.getElementById('historyList');
    const searchInput = document.getElementById('searchInput'); // New: Search input
    // Membuat URL API dinamis. Ini akan berfungsi di localhost dan saat diakses dari luar.
    //const API_BASE_URL = `${window.location.protocol}//${window.location.hostname}:8000`;
    const API_BASE_URL = '';
    // Ambil token dari localStorage
    const token = localStorage.getItem('authToken');
    let allChatHistoryData = []; // New: Store all fetched data
    
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
                    <p class="font-bold text-gray-700">Anda harus login untuk melihat riwayat chat.</p>
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
            allChatHistoryData = chatHistory; // Store all data

            // [FIX] Setelah mengambil data, selalu panggil renderChatHistory untuk menampilkan
            // Ini memastikan search bar bekerja dengan data yang sudah di-render
            // Jika ada search term aktif, terapkan filter sebelum render
            const currentSearchTerm = searchInput.value.toLowerCase();
            const dataToRender = currentSearchTerm ? filterChatHistory(allChatHistoryData, currentSearchTerm) : allChatHistoryData;
            renderChatHistory(dataToRender);

        } catch (error) {
            console.error('Fetch History Error:', error);
            // Hanya tampilkan error jika list masih kosong, agar tidak mengganggu pengguna
            if (historyList.children.length <= 1) {
                historyList.innerHTML = `<li class="liquid-glass rounded-xl p-4 text-center text-red-600">${error.message}. Mungkin sesi Anda telah berakhir, silakan <a href="login.html" class="font-bold underline">login kembali</a>.</li>`;
            }
        }
    }

    // New: Function to render chat history based on provided data
    function renderChatHistory(dataToRender) {
        historyList.innerHTML = ''; // Kosongkan list saat ini

        if (dataToRender.length === 0) {
            historyList.innerHTML = `<li class="liquid-glass rounded-xl p-4 text-center text-gray-600">Tidak ada riwayat chat yang ditemukan.</li>`;
            return;
        }
        
        dataToRender.forEach(chat => {
            const listItem = document.createElement('li');
            listItem.className = 'liquid-glass rounded-xl p-4 flex justify-between items-center';

                // Hapus atribut onclick dari HTML untuk keamanan dan keandalan
                listItem.innerHTML = `
                    <div class="flex-grow cursor-pointer detail-trigger">
                        <p class="font-bold text-gray-800">ID: ${chat.id} - <span class="text-blue-600">${chat.user_message || 'N/A'}</span></p>
                        <p class="text-sm text-gray-500 mt-1">${formatDateTime(chat.waktu)}</p>
                    </div>
                    <div class="flex items-center space-x-2 ml-4">
                        <button class="bg-gray-200 hover:bg-gray-300 rounded-lg p-3 text-gray-700 detail-trigger transition-colors" title="Lihat Detail">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="bg-orange-500 hover:bg-orange-600 rounded-lg p-3 text-white order-trigger transition-colors" title="Tambah ke Orderan">
                            <i class="fas fa-cart-plus"></i>
                        </button>
                    </div>
                `;
                historyList.appendChild(listItem);

                // Tambahkan event listener ke semua elemen pemicu di dalam listItem
                listItem.querySelectorAll('.detail-trigger').forEach(trigger => {
                    trigger.addEventListener('click', () => showChatDetail(formatDateTime(chat.waktu), chat.user_message, chat.bot_response));
                });
                listItem.querySelector('.order-trigger').addEventListener('click', () => showAddOrderModal(chat.user_message, chat.id));
            });

    }

    // New: Helper function to filter chat history
    function filterChatHistory(data, searchTerm) {
    return data.filter(chat => {
        const id = String(chat.id || chat.chat_id || '').toLowerCase();
        const sparepart = String(chat.sparepart_number || chat.part_number || '').toLowerCase();
        const user = (chat.user_message || '').toLowerCase();
        const bot = (chat.bot_response || '').toLowerCase();

        return id.includes(searchTerm) || sparepart.includes(searchTerm) || user.includes(searchTerm) || bot.includes(searchTerm);
    });
}


    // New: Search functionality
    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase();
        const filteredHistory = filterChatHistory(allChatHistoryData, searchTerm);
        renderChatHistory(filteredHistory);
    });

    // Panggil fungsi pertama kali saat halaman dimuat
    fetchAndDisplayHistory().then(() => {
    const searchTerm = searchInput.value.toLowerCase();
    if (searchTerm) {
        const filtered = filterChatHistory(allChatHistoryData, searchTerm);
        renderChatHistory(filtered);
    }
});


    // Atur interval untuk memanggil fungsi setiap 10 detik (10000 milidetik)
    // [FIX] Polling should re-fetch and then re-apply current search filter to the newly fetched data
    window.historyInterval = setInterval(async () => {
        await fetchAndDisplayHistory(); // Re-fetch all data
        const currentSearchTerm = searchInput.value.toLowerCase();
        if (currentSearchTerm) {
            const filteredHistory = filterChatHistory(allChatHistoryData, currentSearchTerm);
            renderChatHistory(filteredHistory);
        } else {
            renderChatHistory(allChatHistoryData); // If no search term, render all
        }
    }, 10000);

    // --- Event Listener untuk Form Tambah Orderan ---
    const addOrderForm = document.getElementById('addOrderForm');
    if (addOrderForm) {
        addOrderForm.addEventListener('submit', async function(event) {
            event.preventDefault();

            const itemName = document.getElementById('orderItemName').textContent;
            const quantity = document.getElementById('orderQuantity').value;
            const chatId = addOrderForm.dataset.chatId; // Ambil chat_id dari dataset
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
                        quantity: parseInt(quantity),
                        chat_id: parseInt(chatId) // Kirim chat_id
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

function showAddOrderModal(itemName, chatId) {
    const addOrderForm = document.getElementById('addOrderForm');
    addOrderForm.dataset.chatId = chatId; // Simpan chat_id di form
    // ... sisa kode di dalam history.html tetap sama
}