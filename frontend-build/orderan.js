document.addEventListener('DOMContentLoaded', function() {
    // Referensi ke elemen-elemen HTML (ini sudah benar untuk quotation.html)
    const tableBody = document.getElementById('orderTableBody');
    const emptyState = document.getElementById('empty-state');
    const loadingRow = document.getElementById('loading-row');
    const grandTotalSection = document.getElementById('grand-total-section');
    const confirmPaymentBtn = document.getElementById('confirmPaymentBtn'); // Tambahkan referensi tombol baru
    const API_BASE_URL = `${window.location.protocol}//${window.location.hostname}:8000`;
    
    const token = localStorage.getItem('authToken');

    // Variabel untuk menyimpan data
    let sparepartData = {}; // { 'part_number': { name: '...', price: ... } }

    let currentAggregatedItems = {}; // Variabel untuk menyimpan item yang diagregasi agar bisa diakses saat konfirmasi
    // --- FUNGSI BANTUAN ---
    function formatRupiah(number) {
        return new Intl.NumberFormat('id-ID', {
            style: 'currency',
            currency: 'IDR',
            minimumFractionDigits: 0
        }).format(number);
    }

    // --- FUNGSI UTAMA ---

    // 1. Fungsi untuk mengambil data master sparepart
    async function fetchSparepartData() {
        if (!token) return;
        try {
            const response = await fetch(`${API_BASE_URL}/api/spareparts`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!response.ok) {
                if (response.status === 401) { // Jika token tidak valid/expired
                    throw new Error('Sesi Anda telah berakhir. Silakan login kembali.');
                }
                throw new Error('Gagal mengambil data master sparepart.');
            }

            const data = await response.json();

            sparepartData = {}; // Kosongkan dulu untuk memastikan data selalu fresh
            data.forEach(part => {
                // Backend sudah membersihkan part_number dan mengonversi price ke angka
                const cleanPartNumber = part.part_number; // part_number sudah bersih dari backend
                if (cleanPartNumber) { // Pastikan part_number tidak null/empty
                    sparepartData[cleanPartNumber] = {
                        name: part.part_name || 'Nama tidak tersedia',
                        price: part.price || 0 // price sudah berupa angka dari backend
                    };
                }
            });

            // --- DEBUGGING ---
            // Buka console (F12) -> tab "Console" untuk melihat ini.
            console.log('--- MASTER SPAREPART DIMUAT (Sudah Angka) ---', sparepartData); // Cek konsol
            // ------------------

        } catch (error) {
            console.error("Error fetching sparepart data:", error);
            throw new Error(`Gagal memuat data master: ${error.message}`);
        }
    }

    // 2. Fungsi untuk mengambil data orderan dan memprosesnya
    async function fetchAndProcessOrders() {
        if (!token) {
            loadingRow.innerHTML = `<td colspan="6" class="text-center py-8">
                <p class="font-bold text-gray-700">Anda harus login untuk melihat orderan.</p>
                <a href="login.html" class="mt-4 inline-block bg-blue-600 text-white font-bold py-2 px-4 rounded-lg hover:bg-blue-700">Login</a>
            </td>`;
            return;
        }

        try {
            const response = await fetch(`${API_BASE_URL}/api/orders/list`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!response.ok) {
                if (response.status === 401) { // Jika token tidak valid/expired
                    throw new Error('Sesi Anda telah berakhir. Silakan login kembali.');
                }
                throw new Error('Gagal mengambil daftar orderan.');
            }
            
            const orders = await response.json();
            processAndRenderTable(orders);

        } catch (error) {
            console.error("Error fetching orders:", error);
            loadingRow.innerHTML = `<td colspan="6" class="text-center py-8 text-red-600">${error.message}</td>`;
        }
    }

    // 3. Fungsi untuk memproses data dan merender tabel
    function processAndRenderTable(orders) {
        if (orders.length === 0) {
            loadingRow.classList.add('hidden');
            emptyState.classList.remove('hidden');
            grandTotalSection.classList.add('hidden');
            return;
        }

        console.log('--- MEMPROSES ORDERAN ---'); // DEBUGGING
        const aggregatedItems = {};

        orders.forEach(order => {
            // Ekstrak nomor sparepart dari 'items'
            const partNumberMatch = order.items.match(/^([^\s(]+)/);
            if (!partNumberMatch) return;

            // Gunakan .trim() untuk membersihkan spasi ekstra dari string order
            const partNumber = partNumberMatch[1].trim(); 

            // Ekstrak qty
            const qtyMatch = order.items.match(/Qty: (\d+)/);
            const qty = qtyMatch ? parseInt(qtyMatch[1]) : 1;

            // --- DEBUGGING ---
            // Buka console (F12) untuk melihat ini.
            // Cek apakah 'partNumber' ini ada di daftar 'MASTER SPAREPART' di atas.
            console.log(`Mencari harga untuk Part Number: "${partNumber}"`);
            const foundPart = sparepartData[partNumber]; // Mencari di master
            
            if (!foundPart) {
                // Jika tidak ditemukan, ini akan muncul di console
                console.warn(`HARGA TIDAK DITEMUKAN untuk: "${partNumber}"`);
            }
            // ------------------

            if (aggregatedItems[partNumber]) {
                // Jika item sudah ada, tambahkan qty dan catat chat_id
                aggregatedItems[partNumber].qty += qty;
                aggregatedItems[partNumber].orderIds.add(order.id);
            } else {
                // Jika item baru, buat entri baru
                aggregatedItems[partNumber] = {
                    partNumber: partNumber,
                    qty: qty,
                    orderIds: new Set([order.id]),
                    // Ambil data dari master sparepart
                    name: foundPart?.name || 'Nama tidak ditemukan',
                    price: foundPart?.price ?? 0, // Gunakan nullish coalescing operator (??) untuk harga, 0 jika null/undefined
                };
                // Tandai harga ditemukan hanya jika part ditemukan DAN harganya bukan null (berarti valid)
                aggregatedItems[partNumber].priceFound = !!foundPart && foundPart.price !== null;
            }
        });

        currentAggregatedItems = aggregatedItems; // Simpan data agregasi
        renderTable(Object.values(aggregatedItems));
    }

    // 4. Fungsi untuk merender baris tabel dan total
    function renderTable(items) {
        tableBody.innerHTML = ''; // Kosongkan tabel
        let subtotal = 0;
        let rowNum = 1;

        items.forEach(item => {
            const totalPerRow = item.qty * item.price;
            // Hanya tambahkan ke subtotal jika harga ditemukan
            if (item.priceFound) {
                subtotal += totalPerRow;
            }
 
            // Tentukan tampilan harga dan total berdasarkan apakah harga ditemukan
            const priceDisplay = item.priceFound ? formatRupiah(item.price) : '<span class="text-red-600 font-semibold">Tidak Ditemukan</span>';
            const totalPerRowDisplay = item.priceFound ? formatRupiah(totalPerRow) : '<span class="text-red-600 font-semibold">N/A</span>';
 
            const orderIdsText = Array.from(item.orderIds).filter(id => id).join(', ');
 
            const row = document.createElement('tr');
            // Tambahkan class jika harga tidak ditemukan untuk styling (misal, latar belakang sedikit merah)
            if (!item.priceFound) {
                row.className = 'bg-red-500/10';
            }
            row.innerHTML = `
                <td class="px-4 py-3">${rowNum++}</td>
                <td class="px-4 py-3">
                    <div class="font-medium">${item.partNumber}</div>
                    <div class="text-xs text-gray-600">Order ID: ${orderIdsText}</div>
                </td>
                <td class="px-4 py-3">${item.name}</td>
                <td class="px-4 py-3 text-center">
                    <input type="number" min="1" value="${item.qty}" class="qty-input w-16 text-center rounded-md p-1">
                </td>
                <td class="px-4 py-3 text-right font-mono">${priceDisplay}</td>
                <td class="px-4 py-3 text-right font-mono font-semibold">${totalPerRowDisplay}</td>
            `;
            tableBody.appendChild(row);
        });

        // Hitung dan tampilkan Grand Total
        const ppn = subtotal * 0.11;
        const total = subtotal + ppn;

        document.getElementById('grand-subtotal').textContent = formatRupiah(subtotal);
        document.getElementById('grand-ppn').textContent = formatRupiah(ppn);
        document.getElementById('grand-total').textContent = formatRupiah(total);
        grandTotalSection.classList.remove('hidden');
    }

    // --- INISIALISASI ---
    async function initialize() {
        try {
            await fetchSparepartData(); // Ambil data master dulu
            await fetchAndProcessOrders(); // Baru ambil dan proses orderan
        } catch (error) {
            // Tangkap error dari salah satu fungsi di atas dan tampilkan di tabel
            let errorMessageHTML = `<td colspan="6" class="text-center py-8 text-red-600">${error.message}</td>`;
            // Jika error karena sesi berakhir, tampilkan tombol login
            if (error.message.includes('Sesi Anda telah berakhir') || error.message.includes('Could not validate credentials')) {
                errorMessageHTML = `<td colspan="6" class="text-center py-8">
                    <p class="font-bold text-gray-700">${error.message}</p>
                    <a href="login.html" class="mt-4 inline-block bg-blue-500 text-white font-bold py-2 px-4 rounded-lg hover:bg-blue-600">Login Ulang</a>
                </td>`;
            }
            loadingRow.innerHTML = errorMessageHTML;
        }
    }

    initialize();

    // Event listener untuk tombol Konfirmasi Pembayaran
    if (confirmPaymentBtn) {
        confirmPaymentBtn.addEventListener('click', function() {
            try {
                console.log("Tombol 'Konfirmasi Pembayaran' diklik.");

                // 1. Ambil elemen total dengan aman
                const totalElement = document.getElementById('grand-total');
                if (!totalElement) {
                    throw new Error("Elemen 'grand-total' tidak ditemukan di HTML.");
                }
                console.log("Langkah 1: Elemen total ditemukan.");

                // 2. Pengecekan data item
                if (!currentAggregatedItems || Object.keys(currentAggregatedItems).length === 0) {
                    throw new Error("Tidak ada data item untuk diproses.");
                }
                console.log("Langkah 2: Data item ditemukan.", currentAggregatedItems);

                // 3. Konversi total menjadi angka
                const totalText = totalElement.textContent;
                const totalAmount = parseFloat(totalText.replace(/[^0-9,]/g, '').replace(',', '.'));
                if (isNaN(totalAmount)) {
                    throw new Error(`Gagal mengonversi total "${totalText}" menjadi angka.`);
                }
                console.log("Langkah 3: Total berhasil dikonversi menjadi angka:", totalAmount);

                // 4. Siapkan data untuk halaman pembayaran
                // [FIX] Konversi Set menjadi Array sebelum stringify
                const itemsForStorage = {};
                for (const key in currentAggregatedItems) {
                    itemsForStorage[key] = {
                        ...currentAggregatedItems[key],
                        orderIds: Array.from(currentAggregatedItems[key].orderIds) // Ubah Set ke Array
                    };
                }
                // [/FIX]

                const paymentDetails = {
                    total: totalAmount,
                    // Gunakan objek yang sudah dikonversi
                    items: itemsForStorage
                };
                console.log("Langkah 4: Data pembayaran siap.", paymentDetails);

                // 5. Simpan ke localStorage dan arahkan halaman
                localStorage.setItem('paymentDetails', JSON.stringify(paymentDetails));
                console.log("Langkah 5: Data disimpan ke localStorage. Mengarahkan ke payment.html...");
                window.location.href = 'payment.html';

            } catch (error) {
                // Jika ada error di langkah mana pun, tampilkan di console dan alert
                console.error("GAGAL PINDAH HALAMAN:", error);
                alert(`Terjadi kesalahan: ${error.message}\n\nSilakan periksa Console (F12) untuk detail teknis.`);
            }
        });
    }
});
