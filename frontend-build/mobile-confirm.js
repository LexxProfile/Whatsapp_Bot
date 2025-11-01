document.addEventListener('DOMContentLoaded', function() {
    const loadingState = document.getElementById('loading-state');
    const mainContent = document.getElementById('main-content');
    const API_BASE_URL = `${window.location.protocol}//${window.location.hostname}:8000`;

    // 1. Ambil transaction_id dari URL
    const urlParams = new URLSearchParams(window.location.search);
    const transactionId = urlParams.get('tx_id');

    if (!transactionId) {
        showError('ID Transaksi tidak valid.');
        return;
    }

    // Tampilkan konten utama
    loadingState.classList.add('hidden');
    mainContent.classList.remove('hidden');
    mainContent.innerHTML = `
        <i class="fas fa-shield-alt text-5xl text-green-600 mb-4"></i>
        <h2 class="text-2xl font-bold mb-2">Konfirmasi Pembayaran</h2>
        <p class="text-gray-600 mb-6">Anda akan mengonfirmasi pembayaran untuk transaksi dengan ID:</p>
        <p class="font-mono bg-white/30 rounded-lg p-2 mb-8 text-sm">${transactionId}</p>
        
        <p class="text-gray-600 mb-4">Pastikan Anda telah menyelesaikan pembayaran sebelum menekan tombol di bawah ini.</p>

        <button id="confirmBtn" class="w-full bg-green-500 hover:bg-green-600 text-white font-bold py-3 px-4 rounded-lg transition-colors text-lg">
            <i class="fas fa-check-circle mr-2"></i>Saya Sudah Bayar
        </button>
        <p id="errorMessage" class="text-red-600 mt-4 text-sm hidden"></p>
    `;

    // 2. Tambahkan event listener ke tombol
    const confirmBtn = document.getElementById('confirmBtn');
    confirmBtn.addEventListener('click', handleConfirmation);

    async function handleConfirmation() {
        confirmBtn.disabled = true;
        confirmBtn.innerHTML = `<i class="fas fa-spinner fa-spin mr-2"></i>Memproses...`;
        document.getElementById('errorMessage').classList.add('hidden');

        try {
            // Tidak perlu token di sini karena ini adalah aksi dari link publik
            const response = await fetch(`${API_BASE_URL}/api/payments/confirm/${transactionId}`, {
                method: 'POST'
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Gagal mengonfirmasi.');
            }

            // Jika berhasil
            mainContent.innerHTML = `
                <i class="fas fa-check-circle text-6xl text-blue-600 mb-4"></i>
                <h2 class="text-2xl font-bold mb-2">Pembayaran Dikonfirmasi!</h2>
                <p class="text-gray-600">Terima kasih! Status pembayaran di halaman sebelumnya akan segera diperbarui. Anda bisa menutup halaman ini.</p>
            `;

        } catch (error) {
            showError(error.message);
            confirmBtn.disabled = false;
            confirmBtn.innerHTML = `<i class="fas fa-check-circle mr-2"></i>Saya Sudah Bayar`;
        }
    }

    function showError(message) {
        loadingState.classList.add('hidden');
        mainContent.classList.remove('hidden');
        const errorEl = document.getElementById('errorMessage');
        if (errorEl) {
            errorEl.textContent = message;
            errorEl.classList.remove('hidden');
        } else {
            mainContent.innerHTML = `<p class="text-red-500">${message}</p>`;
        }
    }
});