document.addEventListener('DOMContentLoaded', function() {
    const historyList = document.getElementById('historyList');
    const loadingState = document.getElementById('loading-state');
    const emptyState = document.getElementById('empty-state');
    const API_BASE_URL = `${window.location.protocol}//${window.location.hostname}:8000`;
    const token = localStorage.getItem('authToken');
    const filterButtons = document.querySelectorAll('.filter-btn');
    
    let activeCountdowns = []; // Untuk menyimpan interval countdown
    let allHistoryData = []; // Menyimpan semua data riwayat
    
    function formatRupiah(number) {
        return new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', minimumFractionDigits: 0 }).format(number);
    }

    function formatDateTime(isoString) {
        if (!isoString) return 'Waktu tidak tersedia';
        return new Date(isoString).toLocaleString('id-ID', { dateStyle: 'long', timeStyle: 'short' });
    }

    // Fungsi untuk memulai timer hitung mundur
    function startCountdown(element, expiresAt, listItem, transactionId) { // Tambahkan transactionId
        const expiryDate = new Date(expiresAt);

        const interval = setInterval(() => {
            const now = new Date();
            const distance = expiryDate - now;

            if (distance < 1000) { // Kurang dari 1 detik
                clearInterval(interval);
                // [FIX] Panggil fungsi untuk memperbarui UI item menjadi Gagal
                if (listItem) {
                    updateListItemToFailed(listItem, transactionId); // Kirim transactionId
                }
                return;
            }

            const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((distance % (1000 * 60)) / 1000);

            element.textContent = `(${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')})`;
        }, 1000);
        activeCountdowns.push(interval); // Simpan interval untuk dibersihkan nanti
    }

    // [BARU] Fungsi untuk memperbarui tampilan item menjadi Gagal
    function updateListItemToFailed(listItem, transactionId) { // Pastikan menerima transactionId
        const statusContainer = listItem.querySelector('.flex.items-center.justify-end.gap-2');
        if (statusContainer) {
            statusContainer.innerHTML = renderStatusBadge('GAGAL');
        }

        // [FIX] Perbarui juga data di allHistoryData agar filter konsisten
        const transactionIndex = allHistoryData.findIndex(tx => tx.id === transactionId);
        if (transactionIndex > -1) {
            allHistoryData[transactionIndex].status = 'GAGAL';
        }

        const continueButton = listItem.querySelector('.continue-payment-btn');
        if (continueButton) {
            continueButton.remove();
        }
    }


    function renderStatusBadge(status) {
        if (status === 'LUNAS') {
            return `<span class="status-badge status-lunas"><i class="fas fa-check-circle mr-1"></i>Lunas</span>`;
        }
        if (status === 'GAGAL') { // [FIX] Ganti Kedaluwarsa menjadi Gagal dengan warna merah
            return `<span class="status-badge" style="background-color: #ef4444; color: white;"><i class="fas fa-times-circle mr-1"></i>Gagal</span>`;
        }
        return `<span class="status-badge status-pending"><i class="fas fa-hourglass-half mr-1"></i>Proses</span>`; // [FIX] Ganti Pending menjadi Proses
    }

    function renderItemDetails(details) {
        if (!details) return '<li>Detail item tidak tersedia.</li>';
        
        let itemsHtml = '';
        try {
            // details bisa jadi string JSON atau sudah objek, tangani keduanya
            const items = typeof details === 'string' ? JSON.parse(details) : details;
            for (const key in items) { // key di sini adalah partNumber
                const item = items[key];
                itemsHtml += `
                    <li class="flex justify-between items-center text-sm py-1">
                        <span>${item.name} (${item.partNumber || key}) (x${item.qty})</span>
                        <span class="font-mono">${formatRupiah(item.price * item.qty)}</span>
                    </li>
                `;
            }
        } catch (e) {
            return '<li>Gagal memuat detail item.</li>';
        }
        return itemsHtml;
    }

    async function fetchHistory() { // Fungsi ini sekarang hanya mengambil data
        if (!token) {
            loadingState.innerHTML = `
                <p class="font-bold">Anda harus login untuk melihat riwayat.</p>
                <a href="login.html" class="mt-4 inline-block bg-blue-500 text-white font-bold py-2 px-4 rounded-lg">Login</a>
            `;
            return;
        }

        try {
            const response = await fetch(`${API_BASE_URL}/api/payments/history`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || 'Gagal memuat riwayat.');
            }

            const historyData = await response.json();
            allHistoryData = historyData; // Simpan semua data
            loadingState.classList.add('hidden');

            if (historyData.length === 0) {
                emptyState.classList.remove('hidden');
                return;
            }

            renderFilteredHistory('ALL'); // Render semua data secara default

        } catch (error) {
            loadingState.innerHTML = `<p class="text-red-600">${error.message}</p>`;
        }
    }

    function renderFilteredHistory(filterStatus) {
        // Hentikan semua countdown yang sedang berjalan sebelum render ulang
        activeCountdowns.forEach(interval => clearInterval(interval));
        activeCountdowns = [];

        // Kosongkan list sebelum render ulang
        historyList.innerHTML = '';
        emptyState.classList.add('hidden');

        let filteredData = allHistoryData;
        if (filterStatus !== 'ALL') {
            filteredData = allHistoryData.filter(tx => tx.status === filterStatus);
        }

        if (filteredData.length === 0) {
            emptyState.classList.remove('hidden');
            return;
        }

        let elementsToCountdown = []; // Kumpulkan elemen yang butuh countdown
        filteredData.forEach(tx => {
            const li = document.createElement('li');
            li.className = 'liquid-glass rounded-xl p-4 cursor-pointer';
            li.innerHTML = `
                <div class="flex justify-between items-center">
                    <div>
                        <p class="font-bold text-gray-800">${formatRupiah(tx.total_amount)}</p>
                        <p class="text-xs text-gray-600 font-mono">${tx.id}</p>
                        <p class="text-xs text-gray-500 mt-1">${formatDateTime(tx.created_at)}</p>
                    </div>
                    <div class="text-right">
                        <div class="flex items-center justify-end gap-2">
                            ${renderStatusBadge(tx.status)}
                            ${ (tx.status === 'PENDING' && tx.expires_at && new Date() < new Date(tx.expires_at))
                                ? `<span id="countdown-${tx.id}" class="text-xs font-mono text-amber-800"></span>`
                                : '' }
                        </div>
                        <i class="fas fa-chevron-down ml-4 transition-transform"></i>
                    </div>
                </div>
                <div class="detail-content mt-3 pt-3 border-t border-white/20">
                    <p class="text-sm font-semibold mb-2">Detail Item:</p>
                    <ul class="space-y-1">
                        ${renderItemDetails(tx.item_details)}
                    </ul>
                    ${
                        (tx.status === 'PENDING' && tx.expires_at && new Date() < new Date(tx.expires_at))
                        ? `<button data-tx-id="${tx.id}" class="continue-payment-btn mt-4 w-full bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded-lg transition-colors">
                            <i class="fas fa-qrcode mr-2"></i>Lanjutkan Pembayaran
                            </button>`
                        : ''
                    }
                </div>
            `;
            historyList.appendChild(li);

            // Jika perlu countdown, tambahkan ke daftar untuk diinisialisasi
            if (tx.status === 'PENDING' && tx.expires_at && new Date() < new Date(tx.expires_at)) {
                elementsToCountdown.push({ id: `countdown-${tx.id}`, expiresAt: tx.expires_at });
            }

            // Event listener untuk expand/collapse detail
            li.addEventListener('click', () => {
                const detail = li.querySelector('.detail-content');
                const icon = li.querySelector('.fa-chevron-down');
                if (detail.style.maxHeight) {
                    detail.style.maxHeight = null;
                    icon.style.transform = 'rotate(0deg)';
                } else {
                    detail.style.maxHeight = detail.scrollHeight + "px";
                    icon.style.transform = 'rotate(180deg)';
                }
            });
        });

        // Tambahkan event listener ke tombol "Lanjutkan Pembayaran" yang baru
        document.querySelectorAll('.continue-payment-btn').forEach(button => {
            button.addEventListener('click', (e) => {
                e.stopPropagation(); // Mencegah event click pada <li> terpicu
                const txId = e.target.closest('button').dataset.txId;
                const transactionData = allHistoryData.find(tx => tx.id === txId);
                if (transactionData) {
                    showQrModal(transactionData);
                }
            });
        });

        // Inisialisasi semua countdown setelah elemen dirender
        elementsToCountdown.forEach(item => {
            const el = document.getElementById(item.id);
            if (el) {
                startCountdown(el, item.expiresAt, el.closest('li'), item.id.replace('countdown-', '')); // Kirim transactionId
            }
        });
    }

    function showQrModal(transaction) {
        // Buat URL konfirmasi untuk QR code
        const confirmationUrl = `${window.location.protocol}//${window.location.hostname}:3000/mobile-confirm.html?tx_id=${transaction.id}`;
        const qrCodeUrl = `https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=${encodeURIComponent(confirmationUrl)}`;

        const isPending = transaction.status === 'PENDING' && new Date() < new Date(transaction.expires_at); // Perbandingan waktu yang konsisten

        // Buat elemen modal
        const modal = document.createElement('div');
        modal.className = 'fixed inset-0 bg-black/60 flex items-center justify-center z-50';
        modal.innerHTML = `
            <div class="liquid-glass rounded-2xl p-8 text-center max-w-sm w-full relative">
                <button class="close-modal-btn absolute top-2 right-4 text-white text-2xl">&times;</button>
                <h3 class="text-xl font-bold text-white mb-4">Lanjutkan Pembayaran</h3>
                
                <div class="flex justify-between items-center bg-white/20 p-3 rounded-lg mb-4">
                    <span class="text-white/80 text-sm">Status:</span>
                    ${renderStatusBadge(transaction.status)}
                </div>

                ${isPending ? `
                    <div class="bg-white p-2 rounded-lg inline-block">
                        <img src="${qrCodeUrl}" alt="QR Code">
                    </div>
                    <p class="text-white/80 text-sm mt-4">Sisa Waktu: <span id="modal-countdown" class="font-bold"></span></p>
                ` : `
                    <div class="h-64 flex flex-col items-center justify-center text-white">
                        <i class="fas fa-exclamation-circle text-5xl mb-4"></i>
                        <p>Pembayaran ini sudah ${transaction.status === 'LUNAS' ? 'lunas' : 'gagal (waktu habis)'}.</p>
                    </div>
                `}
            </div>
        `;

        document.body.appendChild(modal);

        // Mulai countdown di dalam modal jika pending
        if (isPending) {
            const modalCountdownEl = document.getElementById('modal-countdown');
            startCountdown(modalCountdownEl, transaction.expires_at, null, transaction.id); // Tidak perlu update list item dari modal
        }

        const closeModal = () => document.body.removeChild(modal);
        modal.querySelector('.close-modal-btn').addEventListener('click', closeModal);
        modal.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });
    }

    // Inisialisasi event listener untuk filter buttons
    filterButtons.forEach(button => {
        button.addEventListener('click', function() {
            filterButtons.forEach(btn => btn.classList.remove('selected'));
            this.classList.add('selected');
            const filterId = this.id.replace('filter-', '').toUpperCase();
            renderFilteredHistory(filterId);
        });
    });

    fetchHistory();
});
