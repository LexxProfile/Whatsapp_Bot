document.addEventListener('DOMContentLoaded', async function() {
    const loadingState = document.getElementById('loading-state');
    const mainContent = document.getElementById('main-content');
    const API_BASE_URL = '';

    // Fungsi untuk mendapatkan parameter dari URL
    function getUrlParameter(name) {
        name = name.replace(/[\[]/, '\\[').replace(/[\]]/, '\\]');
        const regex = new RegExp('[\\?&]' + name + '=([^&#]*)');
        const results = regex.exec(location.search);
        return results === null ? '' : decodeURIComponent(results[1].replace(/\+/g, ' '));
    }

    const transactionId = getUrlParameter('tx_id');

    if (!transactionId) {
        loadingState.classList.add('hidden');
        mainContent.classList.remove('hidden');
        mainContent.innerHTML = `
            <i class="fas fa-exclamation-triangle text-red-500 text-4xl mb-4"></i>
            <h2 class="text-xl font-bold mb-2">Transaksi Tidak Ditemukan</h2>
            <p class="text-gray-600">ID transaksi tidak valid atau tidak diberikan.</p>
        `;
        return;
    }

    async function fetchTransactionStatus() {
        try {
            const response = await fetch(`${API_BASE_URL}/api/payments/status/${transactionId}`);
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Gagal memuat status transaksi.');
            }
            return await response.json();
        } catch (error) {
            console.error("Error fetching transaction status:", error);
            return { status: 'ERROR', message: error.message };
        }
    }

    async function renderPage(statusData) {
        loadingState.classList.add('hidden');
        mainContent.classList.remove('hidden');

        let contentHtml = '';
        let buttonDisabled = false;
        let buttonText = 'Konfirmasi Pembayaran';
        let buttonClass = 'bg-blue-600 hover:bg-blue-700';

        if (statusData.status === 'LUNAS') {
            contentHtml = `
                <i class="fas fa-check-circle text-green-500 text-4xl mb-4"></i>
                <h2 class="text-xl font-bold mb-2">Pembayaran Berhasil!</h2>
                <p class="text-gray-600">Terima kasih, pembayaran Anda telah dikonfirmasi.</p>
            `;
            buttonDisabled = true;
            buttonText = 'Pembayaran Sudah Dikonfirmasi';
            buttonClass = 'bg-gray-400 cursor-not-allowed';
        } else if (statusData.status === 'EXPIRED' || statusData.status === 'GAGAL') {
            contentHtml = `
                <i class="fas fa-times-circle text-red-500 text-4xl mb-4"></i>
                <h2 class="text-xl font-bold mb-2">Pembayaran Gagal / Kedaluwarsa</h2>
                <p class="text-gray-600">Sesi pembayaran ini sudah tidak berlaku.</p>
            `;
            buttonDisabled = true;
            buttonText = 'Sesi Kedaluwarsa';
            buttonClass = 'bg-gray-400 cursor-not-allowed';
        } else if (statusData.status === 'PENDING') {
            contentHtml = `
                <i class="fas fa-hourglass-half text-blue-500 text-4xl mb-4"></i>
                <h2 class="text-xl font-bold mb-2">Menunggu Konfirmasi</h2>
                <p class="text-gray-600 mb-6">Silakan klik tombol di bawah untuk mengonfirmasi pembayaran Anda.</p>
            `;
        } else {
            contentHtml = `
                <i class="fas fa-exclamation-circle text-yellow-500 text-4xl mb-4"></i>
                <h2 class="text-xl font-bold mb-2">Status Tidak Diketahui</h2>
                <p class="text-gray-600">Terjadi kesalahan atau status transaksi tidak jelas.</p>
                <p class="text-red-500 text-sm mt-2">${statusData.message || ''}</p>
            `;
            buttonDisabled = true;
            buttonText = 'Tidak Dapat Dikonfirmasi';
            buttonClass = 'bg-gray-400 cursor-not-allowed';
        }

        mainContent.innerHTML = `
            ${contentHtml}
            <button id="confirmBtn" class="mt-6 w-full text-white font-bold py-3 px-4 rounded-lg transition-colors ${buttonClass}" ${buttonDisabled ? 'disabled' : ''}>
                ${buttonText}
            </button>
        `;

        if (!buttonDisabled) {
            document.getElementById('confirmBtn').addEventListener('click', async () => {
    try {
        const response = await fetch(
            `${API_BASE_URL}/api/payments/confirm/${transactionId}`,
            { method: 'POST' }
        );

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Gagal mengonfirmasi pembayaran.');
        }

        alert('Pembayaran berhasil dikonfirmasi!');
        location.reload();

    } catch (error) {
        alert(`Error: ${error.message}`);
        console.error(error);
    }
});

        }
    }

    const status = await fetchTransactionStatus();
    renderPage(status);
});