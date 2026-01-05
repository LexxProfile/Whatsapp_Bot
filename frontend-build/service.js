/* services.js - FINAL FIXED VERSION 2.0 */

// --- KONFIGURASI ---
const API_BASE_URL = window.API_BASE_URL || 'https://endlessproject.my.id'; // Use global API_BASE_URL, fallback if not defined
let token = localStorage.getItem('authToken');

// Variabel Data Global
let allItemsData = [];
let cart = [];
let currentCar = JSON.parse(localStorage.getItem('currentCar')) || null;
let customerDetails = JSON.parse(localStorage.getItem('customerDetails')) || {};
// Data Mobil (UI)
const carData = [
    { 
        model: "TIGGO CROSS", 
        image: "https://cheryidn.sgp1.cdn.digitaloceanspaces.com/prod/product-models/tiggo/product-types/tiggo-cross/thumbnail-front-image-desktop.webp" 
    }, // 
    { 
        model: "TIGGO CROSS CSH", 
        image: "https://cheryidn.sgp1.cdn.digitaloceanspaces.com/prod/product-models/product-list-nov/Tiggo-Cross-CSH.png" 
    }, // 
    { 
        model: "TIGGO 5X", 
        image: "" 
    }, // Tidak ada data di source
    { 
        model: "Tiggo 7 Luxury", 
        image: "" 
    }, // Tidak ada data di source
    { 
        model: "Tiggo 7 comfort", 
        image: "" 
    }, // Tidak ada data di source
    { 
        model: "Tiggo 7 premium", 
        image: "" 
    }, // Tidak ada data di source
    { 
        model: "Tiggo 8 Pro", 
        image: "https://cheryidn.sgp1.cdn.digitaloceanspaces.com/prod/product-models/tiggo/product-types/tiggo-8/thumbnail-front-image-desktop.png" 
    }, // Menggunakan gambar TIGGO 8 sesuai instruksi varian 
    { 
        model: "Tiggo 8 Pro LUXURY", 
        image: "https://cheryidn.sgp1.cdn.digitaloceanspaces.com/prod/product-models/tiggo/product-types/tiggo-8/thumbnail-front-image-desktop.png" 
    }, // Menggunakan gambar TIGGO 8 sesuai instruksi varian 
    { 
        model: "Tiggo 8 Pro MAX", 
        image: "https://cheryidn.sgp1.cdn.digitaloceanspaces.com/prod/product-models/product-list-nov/Tiggo-8-Pro-Max.png" 
    }, // 
    { 
        model: "Tiggo 8 CSH", 
        image: "https://cheryidn.sgp1.cdn.digitaloceanspaces.com/prod/product-models/tiggo/product-types/tiggo-8-csh/thumbnail-front-image-desktop.webp" 
    }, // 
    { 
        model: "Tiggo 8 1.6 COMFORT", 
        image: "https://cheryidn.sgp1.cdn.digitaloceanspaces.com/prod/product-models/tiggo/product-types/tiggo-8/thumbnail-front-image-desktop.png" 
    }, // Menggunakan gambar TIGGO 8 
    { 
        model: "Tiggo 8 1.6 PREMIUM", 
        image: "https://cheryidn.sgp1.cdn.digitaloceanspaces.com/prod/product-models/tiggo/product-types/tiggo-8/thumbnail-front-image-desktop.png" 
    }, // Menggunakan gambar TIGGO 8 
    { 
        model: "OMODA C5 RZ", 
        image: "https://cheryidn.sgp1.cdn.digitaloceanspaces.com/prod/product-models/omoda/product-types/c5/c5-front-thumbnail.png" 
    }, // Menggunakan gambar CHERY C5 
    { 
        model: "OMODA C5 Z", 
        image: "https://cheryidn.sgp1.cdn.digitaloceanspaces.com/prod/product-models/omoda/product-types/c5/c5-front-thumbnail.png" 
    }, // Menggunakan gambar CHERY C5 
    { 
        model: "J6 RWD", 
        image: "https://cheryidn.sgp1.cdn.digitaloceanspaces.com/prod/product-models/product-list-nov/J6.png" 
    }, // 
    { 
        model: "J6 IWD", 
        image: "https://cheryidn.sgp1.cdn.digitaloceanspaces.com/prod/product-models/product-list-nov/J6.png" 
    }, // 
    { 
        model: "TIGGO 9 CSH", 
        image: "https://cheryidn.sgp1.cdn.digitaloceanspaces.com/prod/main-images/Tiggo%209%20CSH.png" 
    }, // 
    { 
        model: "OMODA 5 Z", 
        image: "https://cheryidn.sgp1.cdn.digitaloceanspaces.com/prod/product-models/omoda/product-types/c5/c5-front-thumbnail.png" 
    }, // Menggunakan gambar CHERY C5 
    { 
        model: "OMODA 5 RZ", 
        image: "https://cheryidn.sgp1.cdn.digitaloceanspaces.com/prod/product-models/omoda/product-types/c5/c5-front-thumbnail.png" 
    }, // Menggunakan gambar CHERY C5 
    { 
        model: "OMODA 5 GT FWD", 
        image: "https://cheryidn.sgp1.cdn.digitaloceanspaces.com/prod/product-models/product-list-nov/Omoda-5-GT-AWD.png" 
    }, // 
    { 
        model: "OMODA 5 GT AWD", 
        image: "https://cheryidn.sgp1.cdn.digitaloceanspaces.com/prod/product-models/product-list-nov/Omoda-5-GT-AWD.png" 
    }, // 
    { 
        model: "OMODA 5 EV", 
        image: "https://cheryidn.sgp1.cdn.digitaloceanspaces.com/prod/product-models/omoda/product-types/omoda-e5/thumbnail-front-image-desktop.webp" 
    }, // Menggunakan gambar CHERY E5 
];

// --- FUNGSI UTILITY ---
function saveData() {
    localStorage.setItem('currentServiceInvoice', JSON.stringify(cart));
    localStorage.setItem('currentCar', JSON.stringify(currentCar));
}

function showMessage(msg) {
    const toast = document.createElement('div');
    toast.textContent = msg;
    toast.className = 'fixed top-5 right-5 bg-gray-800 text-white px-4 py-2 rounded shadow-lg z-[100] text-sm animate-fade-in-down';
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// --- FUZZY MATCHING LOGIC ---
function shouldIncludeService(serviceTipe, selectedModel) {
    if (!serviceTipe) return false;

    const dbTag = serviceTipe.toUpperCase().trim();
    const selected = selectedModel.toUpperCase().trim();

    // 1. Kondisi Mutlak: ALL MODEL atau Exact Match
    if (dbTag === 'ALL MODEL' || dbTag === 'ALL' || dbTag === selected) {
        return true;
    }

    // 2. KONDISI PENGECUALIAN (STRICT MATCH)
    // Jika model yang dipilih SANGAT SPESIFIK (misal PRO MAX), kita hanya ambil exact match.
    if (selected.includes('PRO MAX') || selected.includes('EV')) {
        return false; // Karena sudah di cek di atas, jika bukan exact match, kita tolak
    }

    // 3. KONDISI FUZZY (Tiggo 8 harus cocok dengan semua Tiggo 8)
    let genericRoot = '';
    
    // Simplifikasi: Ambil 2-3 kata pertama (misal 'CHERY TIGGO 8 PRO' -> 'TIGGO 8')
    if (selected.includes('OMODA 5')) {
        genericRoot = 'OMODA 5';
    } else if (selected.includes('TIGGO 8')) {
        genericRoot = 'TIGGO 8';
    } else if (selected.includes('TIGGO 7')) {
        genericRoot = 'TIGGO 7';
    } else if (selected.includes('TIGGO CROSS')) {
        genericRoot = 'TIGGO CROSS';
    }

    // Final Check Fuzzy (jika tag database mengandung root generic)
    if (genericRoot && dbTag.includes(genericRoot)) {
        return true;
    }

    return false;
}

// --- API FETCH DATA ---
// --- FUNGSI API (BACKEND) ---
// PERHATIKAN PENAMBAHAN KEY BARU DARI DATABASE: tipe_kendaraan, flat_rate, labor_charge
// --- FUNGSI API (BACKEND) YANG SUDAH DIPERBAIKI ---
// --- FUNGSI API (BACKEND) YANG SUDAH DIPERBAIKI (FINAL) ---
async function fetchAllData(carModel = null) {
    const tokenLocal = localStorage.getItem('authToken');
    if (!tokenLocal) {
        alert("Sesi habis, silakan login ulang.");
        window.location.href = 'index.html';
        return [];
    }

    try {
        let sparepartUrl = carModel 
             ? `${API_BASE_URL}/api/spareparts/by-type?type=${encodeURIComponent(carModel)}`
             : `${API_BASE_URL}/api/spareparts`;

        // FIX 1: Kirim carModel ke API Services untuk filtering di Backend
        let servicesUrl = `${API_BASE_URL}/api/services`;
        if (carModel) {
            servicesUrl += `?car_model=${encodeURIComponent(carModel)}`;
        }
        // ------------------------------------------------------------------

        const authHeaders = { 'Authorization': `Bearer ${tokenLocal}` };

        const [sparepartRes, serviceRes] = await Promise.all([
            fetch(sparepartUrl, { headers: authHeaders }),
            fetch(servicesUrl, { headers: authHeaders }) // Gunakan URL Services yang sudah ada filternya
        ]);

        // CEK AUTENTIKASI (401)
        if (sparepartRes.status === 401 || serviceRes.status === 401) {
            alert("Sesi Anda habis. Silakan login ulang.");
            window.location.href = 'index.html';
            return []; 
        }
        
        // CEK RESPON SERVER LAINNYA (Misal 500 atau 404)
        if (!sparepartRes.ok && sparepartRes.status !== 404 || !serviceRes.ok && serviceRes.status !== 404) {
             throw new Error('API_FETCH_FAILED');
        }

        const spareparts = sparepartRes.ok ? await sparepartRes.json() : [];
        const services = serviceRes.ok ? await serviceRes.json() : [];

        // --- FORMAT DATA ---
        const formattedSpareparts = (Array.isArray(spareparts) ? spareparts : []).map(item => ({
            code: item.part_number || '',
            name: item.part_name || '',
            price: typeof item.price === 'number' ? item.price : Number(item.price) || 0,
            type: 'sparepart',
            label: 'Pcs',
            quantity: 1 
        }));

        const formattedServices = (Array.isArray(services) ? services : []).map(item => {
            const hourlyRate = item.lc_per_hour ? Number(item.lc_per_hour) : 0;
            
            return {
                code: item.code || '',
                name: item.name || '', 
                price: typeof item.price === 'number' ? item.price : Number(item.price) || 0,
                type: 'service',
                label: 'Jam',
                duration:100,               
                // --- KOLOM UNTUK FILTERING ---
                tipe_kendaraan: item.tipe_kendaraan || 'ALL MODEL',
                lc_per_hour: hourlyRate, 
                flat_rate: item.flat_rate ? Number(item.flat_rate) : 0,
            };
        });

        allItemsData = [...formattedServices, ...formattedSpareparts];
        return allItemsData;
        
    } catch (error) {
        if (error.message === 'API_FETCH_FAILED') {
            showMessage("Gagal mengambil data dari salah satu API.");
        } else {
            console.error("Error fetching data:", error);
        }
        return [];
    }
}

// --- PERUBAHAN TAMBAHAN (Wajib) ---
// Perbarui fungsi addToCart agar menggunakan default 100 menit.
// Ganti fungsi addToCart di services.js Anda:
// --- CORE: CART LOGIC ---
function addToCart(code) {
    const item = allItemsData.find(i => i.code === code);
    if (!item) {
        showMessage('Item tidak ditemukan di sistem lokal');
        return;
    }
    const existing = cart.find(c => c.code === code);
    
    if (existing) {
        // Jika item sudah ada, hanya tambah 1 menit/pcs
        const increment = item.type === 'service' ? 1 : 1; 
        existing.quantity = (existing.quantity || 0) + increment;
    } else {
        const fullItem = allItemsData.find(i => i.code === code);
        
        // LOGIKA BARU: Default quantity Jasa = 100 menit
        const defaultQty = item.type === 'service' ? 100 : 1; 
        
        cart.push({ ...fullItem, quantity: defaultQty });
    }
    
    saveData();    // Refresh UI
    if (window.location.pathname.includes('detail.html')) {
        renderSelectedItems();
        updateConfirmButton();
    }
}


window.updateCartQuantity = function(code, delta) {
    const item = cart.find(c => c.code === code);
    if (item) {
        const newQty = (item.quantity || 1) + delta;
        if (newQty <= 0) {
            removeFromCart(code);
        } else {
            item.quantity = newQty;
            saveData();
            renderSelectedItems();
            updateConfirmButton();
        }
    }
}

window.updateCartQuantityInput = function(code, value) {
    const item = cart.find(c => c.code === code);
    const newQty = parseInt(value);
    if (item && !isNaN(newQty) && newQty > 0) {
        item.quantity = newQty;
        saveData();
        renderSelectedItems();
        updateConfirmButton();
    } else if (item && newQty <= 0) {
        removeFromCart(code);
    }
}

window.removeFromCart = function(code) {
    cart = cart.filter(i => i.code !== code);
    saveData();
    renderSelectedItems();
    updateConfirmButton();
}

// --- services.js ---

function setupItemSearch(inputId, dropdownId, sourceData, itemType) {
    const input = document.getElementById(inputId);
    const dropdown = document.getElementById(dropdownId);
    if(!input || !dropdown) return;

    const renderDropdown = (items) => {
        dropdown.innerHTML = '';
        
        // --- LOGIKA TOMBOL TAMBAH JASA (JIKA KOSONG) ---
        if (items.length === 0) {
            // Jika tidak ada hasil DAN sedang mencari JASA: Tampilkan tombol 'Tambah Baru'
            if (itemType === 'service') {
                dropdown.innerHTML = `
                    <div class="p-4 text-center bg-white">
                        <p class="text-gray-500 text-sm mb-3">"${input.value}" tidak ditemukan.</p>
                        <button onclick="openJasaModal('${input.value}')" class="text-sm bg-red-50 text-red-600 px-4 py-2 rounded-full font-semibold hover:bg-red-100 transition w-full border border-red-200">
                            + Tambah Jasa Baru
                        </button>
                    </div>
                `;
            } else {
                dropdown.innerHTML = `<div class="p-3 text-gray-500 bg-white">Tidak ada hasil.</div>`;
            }
            dropdown.classList.remove('hidden'); 
            return;
        }

        // Tampilkan maks 10 item
        items.slice(0, 10).forEach(item => { 
            
            // Tentukan harga yang akan ditampilkan dan label unit
            // FIX: Mengambil LC PER HOUR (rate dasar) untuk display jasa
            const displayPrice = item.type === 'service' ? item.lc_per_hour : item.price;
            const priceLabel = item.type === 'service' ? '/100 mnt' : '/pcs';
            
            const el = document.createElement('div');
            el.className = 'p-3 hover:bg-gray-100 bg-white cursor-pointer flex justify-between items-center border-b border-gray-100 last:border-0';
            
            el.innerHTML = `
                <div>
                    <div class="font-medium text-gray-800">${item.name}</div>
                    <div class="text-sm text-gray-500">
                        <span class="bg-gray-100 text-gray-600 px-1 rounded border text-xs mr-1">${item.code}</span> 
                        | Rp ${displayPrice.toLocaleString('id-ID')} ${priceLabel}
                    </div>
                </div>
            `;
            
            // KLIK ITEM: Masukkan ke cart & Bersihkan Search Bar
            el.addEventListener('click', () => {
                addToCart(item.code);
                input.value = ''; 
                dropdown.classList.add('hidden'); 
            });
            dropdown.appendChild(el);
        });
        dropdown.classList.remove('hidden');
    };

    input.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase();
        if (query.length < 1) { 
            dropdown.classList.add('hidden');
            return;
        }
        const results = sourceData.filter(item => {
            const nameMatch = item.name && item.name.toLowerCase().includes(query);
            const codeMatch = item.code && String(item.code).toLowerCase().includes(query);
            return nameMatch || codeMatch;
        });
        renderDropdown(results);
    });

    // Tutup jika klik di luar
    document.addEventListener('click', (e) => {
        if (!dropdown.contains(e.target) && e.target !== input) {
            dropdown.classList.add('hidden');
        }
    });
}



function createCartItemElement(item) {
    const el = document.createElement('div');
    el.className = 'flex justify-between items-center bg-gray-50 p-3 rounded-lg border border-gray-200';
    
    const unitPrice = item.price || 0;
    let totalItemPrice = 0;
    let unitLabel = '';
    let step = 1;

    // Ambil Tipe Kendaraan dari item (untuk display validasi)
    const carTypeValidation = item.tipe_kendaraan ? item.tipe_kendaraan.toUpperCase() : 'ALL MODEL';
    const baseRate = item.lc_per_hour || 0;
    // --- LOGIKA PERHITUNGAN MENIT (BASIS 100) VS PCS ---
    if (item.type === 'service') {
        // FIX: Gunakan baseRate (lc_per_hour) untuk perhitungan
        totalItemPrice = (baseRate / 100) * (item.quantity || 100); 
        unitLabel = 'mnt';
        step = 1;
    } else {
        // Rumus Sparepart: Harga * Pcs
        totalItemPrice = unitPrice * (item.quantity || 1);
        unitLabel = 'pcs';
        step = 1; 
    }

    const priceDisplay = Math.round(totalItemPrice).toLocaleString('id-ID');

    el.innerHTML = `
        <div class="flex-1 min-w-0 pr-2">
            <div class="font-semibold text-gray-800 truncate">${item.name}</div>
            
            <div class="text-xs text-gray-500 mt-1">
                <span class="bg-purple-100 text-purple-700 px-2 py-0.5 rounded font-medium mr-2">${carTypeValidation}</span>
                
                ${item.type === 'service' ? 
                    // LABEL: Rate per 100 mnt
                    `Rate: Rp ${item.lc_per_hour.toLocaleString('id-ID')}/100 mnt` : 
                    `@ Rp ${unitPrice.toLocaleString('id-ID')}/pcs`}
            </div>
            
            <div class="text-sm text-red-600 font-bold">Total: Rp ${priceDisplay}</div>
        </div>
        <div class="flex items-center gap-2 flex-shrink-0">
            <button onclick="updateCartQuantity('${item.code}', -${step})" class="text-red-500 font-bold p-1 border rounded w-8 bg-white">-</button>
            <input type="number" value="${item.quantity}" min="1" onchange="updateCartQuantityInput('${item.code}', this.value)" class="w-14 text-center border rounded text-sm py-1">
            <span class="text-xs text-gray-500 w-6">${unitLabel}</span>
            <button onclick="updateCartQuantity('${item.code}', ${step})" class="text-green-600 font-bold p-1 border rounded w-8 bg-white">+</button>
            <button onclick="removeFromCart('${item.code}')" class="ml-2 text-gray-400 hover:text-red-500"><i class="fas fa-trash"></i></button>
        </div>
    `;
    return el;
}

// --- RENDER CART UI (SUDAH DIPERBAIKI) ---
// --- RENDER CART UI ---
function renderSelectedItems() {
    const sparepartContainer = document.getElementById('selectedSpareparts');
    const jasaContainer = document.getElementById('selectedJasa');
    if (!sparepartContainer || !jasaContainer) return;
    
    sparepartContainer.innerHTML = '';
    jasaContainer.innerHTML = '';

    const sparepartsInCart = cart.filter(i => i.type === 'sparepart');
    const servicesInCart = cart.filter(i => i.type === 'service');
    
    if (sparepartsInCart.length > 0) {
        // Baris 338 Anda memanggil fungsi ini: Pastikan sudah didefinisikan sebelumnya!
        sparepartsInCart.forEach(item => sparepartContainer.appendChild(createCartItemElement(item)));
    }
    if (servicesInCart.length > 0) {
        servicesInCart.forEach(item => jasaContainer.appendChild(createCartItemElement(item)));
    }
}

// --- services.js ---



// --- TOMBOL KONFIRMASI ---
// --- services.js ---

function updateConfirmButton() {
    const confirmBtn = document.getElementById('confirmBtn');
    if (!confirmBtn) return;
    
    // Hitung Total Uang
    const totalHarga = cart.reduce((total, item) => {
        if (item.type === 'service') {
            // FIX: Gunakan item.lc_per_hour untuk rate dasar moneter
            const ratePerUnit = item.lc_per_hour / 100; 
            return total + (ratePerUnit * (item.quantity || 0)); 
        } else {
            return total + ((item.price || 0) * (item.quantity || 0));
        }
    }, 0);

    const totalQty = cart.length;

    if (totalQty > 0) {
        confirmBtn.classList.remove('hidden');
        confirmBtn.innerHTML = `✓ Konfirmasi Invoice Rp ${Math.round(totalHarga).toLocaleString('id-ID')}`;
        
        confirmBtn.onclick = () => {
             saveData();
             window.location.href = 'invoice.html';
        };
    } else {
        confirmBtn.classList.add('hidden');
    }
}

// --- PAGE INITIALIZATION ---
async function initDetailPageUI() {
    const title = document.getElementById('detailTitle');
    
    // 1. Cek Mobil dan Redirect
    if (!currentCar) {
         window.location.href = 'estimasi_jasa.html';
         return; 
    }
    
    // Set Judul
    title.innerHTML = `Estimasi Jasa: ${currentCar.model}`;

    // --- LOGIKA DATA PELANGGAN (FIXED) ---
    const customerDetails = JSON.parse(localStorage.getItem('customerDetails')) || {};
    const customerForm = document.getElementById('customerForm'); // Ambil elemen form
    
    // Ambil semua input fields
    const nameInput = document.getElementById('customerName');
    const plateInput = document.getElementById('customerPlate');
    const phoneInput = document.getElementById('customerPhone');
    const noteInput = document.getElementById('customerNote');

    // Isi Input Fields dengan data yang tersimpan (Load)
    if (nameInput) nameInput.value = customerDetails.name || '';
    if (plateInput) plateInput.value = customerDetails.plate || '';
    if (phoneInput) phoneInput.value = customerDetails.phone || '';
    if (noteInput) noteInput.value = customerDetails.note || '';

    // Pasang Listener untuk menyimpan data saat user mengetik
    if (customerForm) {
        customerForm.addEventListener('input', saveCustomerDetails); 
    }
    // --- AKHIR LOGIKA DATA PELANGGAN ---

    // Tampilkan Loading State
    const sparepartContainer = document.getElementById('selectedSpareparts');
    const jasaContainer = document.getElementById('selectedJasa');
    if (sparepartContainer) sparepartContainer.innerHTML = '<div class="text-center py-4 text-gray-500"><i class="fas fa-spinner fa-spin mr-2"></i>Memuat data...</div>';
    
    // Fetch Data
    const data = await fetchAllData(currentCar.model);
    
    // Filter Data
    let filteredSpareparts = data.filter(item => item.type === 'sparepart');
    let filteredServices = data.filter(item => item.type === 'service');

    // Setup Search UIs
    setupItemSearch('sparepartSearch', 'sparepartDropdown', filteredSpareparts, 'sparepart');
    setupItemSearch('jasaSearch', 'jasaDropdown', filteredServices, 'service');

    // Render Cart and Update Confirmation Button
    renderSelectedItems();
    updateConfirmButton(); // Cek tombol saat load
}

function renderCarCards() {
    const container = document.getElementById('listContainer');
    if(!container) return; 
    
    container.innerHTML = carData.map(car => `
        <div class="service-card bg-white p-6 rounded-xl shadow hover:shadow-lg transition cursor-pointer text-center" onclick="selectCar('${car.model.replace(/'/g, "\\'")}')">
            <div class="mb-4 flex justify-center items-center h-32"><img src="${car.image}" alt="${car.model}" class="max-h-full max-w-full object-contain"></div>
            <h3 class="text-xl font-bold text-gray-800">${car.model}</h3>
            <p class="text-gray-500 text-sm mt-2">Klik untuk estimasi</p>
        </div>
    `).join('');
}

window.selectCar = async function(model) {
    const prevCar = JSON.parse(localStorage.getItem('currentCar'));
    if (prevCar && prevCar.model !== model) {
        cart = [];
        localStorage.setItem('currentServiceInvoice', JSON.stringify([]));
    }
    const car = carData.find(c => c.model === model);
    currentCar = car;
    localStorage.setItem('currentCar', JSON.stringify(currentCar));
    window.location.href = 'detail.html';
};

function filterCarCards() {
    const searchInput = document.getElementById('searchBar');
    const container = document.getElementById('listContainer');
    if (!searchInput || !container) return;

    const query = searchInput.value.toLowerCase().trim();

    // 1. Filter array carData global
    const filteredCars = carData.filter(car => 
        car.model.toLowerCase().includes(query)
    );

    // 2. Buat ulang HTML cards berdasarkan hasil filter
    container.innerHTML = filteredCars.map(car => `
        <div class="service-card bg-white p-6 rounded-xl shadow hover:shadow-lg transition cursor-pointer text-center" onclick="selectCar('${car.model.replace(/'/g, "\\'")}')">
            <div class="mb-4 flex justify-center items-center h-32"><img src="${car.image}" alt="${car.model}" class="max-h-full max-w-full object-contain"></div>
            <h3 class="text-xl font-bold text-gray-800">${car.model}</h3>
            <p class="text-gray-500 text-sm mt-2">Klik untuk estimasi</p>
        </div>
    `).join('');

    // Tampilkan pesan jika tidak ada hasil
    if (filteredCars.length === 0 && query.length > 0) {
        container.innerHTML = `<p class="text-center text-xl text-gray-600 col-span-full py-10">Tipe mobil **"${query}"** tidak ditemukan.</p>`;
    }
}

// --- LOGIKA MODAL TAMBAH JASA (SUDAH DIPERBAIKI) ---

window.openJasaModal = function(prefillName = '') {
    const modal = document.getElementById('addJasaModal');
    const nameInput = document.getElementById('newJasaName');
    if(nameInput) nameInput.value = prefillName; 
    if(modal) modal.classList.remove('hidden');
    
    // FIX: Panggil kalkulasi pada input Durasi atau Biaya Akhir yang baru
    const durationInput = document.getElementById('newJasaDuration');
    if (durationInput) {
        // Memicu event 'input' agar display rate per menit (Rp 0) langsung muncul
        durationInput.dispatchEvent(new Event('input')); 
    }
}

window.closeJasaModal = function() {
    const modal = document.getElementById('addJasaModal');
    if(modal) modal.classList.add('hidden');
    document.getElementById('addJasaForm').reset();
}

// Catatan: Baris di bawah ini tidak perlu di scope global, 
// biasanya dipindahkan ke fungsi initDetailPageUI. Saya biarkan di sini jika Anda membutuhkannya.
const searchInput = document.getElementById('jasaSearch');
const dropdown = document.getElementById('jasaDropdown');
if(searchInput) searchInput.value = '';
if(dropdown) dropdown.classList.add('hidden');


// --- HANDLE SUBMIT FORM TAMBAH JASA BARU ---
// --- LOGIKA KALKULASI DAN SUBMIT BARU ---

// Fungsi utilitas untuk update display rate dasar (Biaya Per Menit)
// --- LOGIKA KALKULASI DISPLAY RATE PER 100 MENIT ---

// Fungsi utilitas untuk update display rate dasar
// Fungsi utilitas untuk update display rate dasar
// --- LOGIKA KALKULASI DISPLAY RATE PER 100 MENIT (HELPER) ---

function updateCalculatedRateDisplay() {
    const durationEl = document.getElementById('newJasaDuration');
    const chargeEl = document.getElementById('newJasaLaborCharge');
    const displayEl = document.getElementById('calculatedRateDisplay');
    
    // Cek apakah elemen input modal sudah ada
    if (!durationEl || !chargeEl || !displayEl) return;
    
    const duration = parseFloat(durationEl.value || 0);
    const charge = parseFloat(chargeEl.value || 0);
    
    if (duration > 0 && !isNaN(charge)) {
        // RUMUS: Base Rate Per 100 Mnt = (Labor Charge / Duration Menit) * 100
        const calculatedRate = (charge / duration) * 100;
        
        // Tampilkan hasil kalkulasi ke user
        displayEl.innerHTML = `Base Rate (LC/100 Mnt): **Rp ${Math.round(calculatedRate).toLocaleString('id-ID')}**`;
    } else {
        displayEl.innerHTML = `Base Rate: Rp 0`;
    }
}

// Pasang listener kalkulasi real-time saat DOM content dimuat
document.addEventListener('DOMContentLoaded', () => {
    // Pastikan kode ini dieksekusi setelah semua elemen HTML ada
    
    const durationInput = document.getElementById('newJasaDuration');
    const laborChargeInput = document.getElementById('newJasaLaborCharge');
    
    if (durationInput && laborChargeInput) {
        // Pasang event listener untuk memicu update setiap ada ketikan
        durationInput.addEventListener('input', updateCalculatedRateDisplay);
        laborChargeInput.addEventListener('input', updateCalculatedRateDisplay);
        
        // Panggil sekali saat load
        setTimeout(updateCalculatedRateDisplay, 1000); 
    }
});


// --- HANDLE SUBMIT FORM TAMBAH JASA BARU ---
document.getElementById('addJasaForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    // Ambil Input
    const name = document.getElementById('newJasaName').value;
    const durationInput = document.getElementById('newJasaDuration').value; 
    const laborChargeInput = document.getElementById('newJasaLaborCharge').value;
    
    // Konversi dan Validasi
    const duration = parseFloat(durationInput);
    const finalCharge = parseFloat(laborChargeInput);
    
    if (duration <= 0 || isNaN(duration)) {
        alert("Durasi (Menit) harus angka yang valid dan lebih dari 0.");
        return;
    }
    
    // Hitung Base Rate yang akan dikirim ke Backend (price)
    // Formula: (FinalCharge / Duration) * 100
    const calculatedBaseRate = (finalCharge / duration) * 100;
    
    const submitBtn = e.target.querySelector('button[type="submit"]');
    
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = 'Menyimpan...';
    submitBtn.disabled = true;

    try {
        // 1. Kirim Payload ke Backend (Menggunakan nama kolom database)
        // ASUMSI: Backend sudah diupdate untuk menerima jenis_pekerjaan, lc_per_hour, flat_rate, labor_charge
        const res = await fetch(`${API_BASE_URL}/api/services/add`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('authToken')}`
            },
            body: JSON.stringify({ 
                jenis_pekerjaan: name, 
                lc_per_hour: calculatedBaseRate, 
                flat_rate: duration, 
                labor_charge: finalCharge 
            }) 
        });

        if (!res.ok) throw new Error('Gagal menyimpan di server.');
        const newItem = await res.json();
        
        // 2. Format Item Baru untuk Cart Lokal
        const formattedItem = {
            code: newItem.code,
            name: name,
            price: calculatedBaseRate, // Base Rate
            type: 'service', 
            quantity: duration, 
            lc_per_hour: calculatedBaseRate, 
            flat_rate: duration, 
            labor_charge: finalCharge 
        };

        // 3. Tambah ke data lokal & Cart
        allItemsData.push(formattedItem); 
        addToCart(formattedItem.code);

        // 4. Tutup dan Bersihkan UI
        closeJasaModal();
        const searchInput = document.getElementById('jasaSearch');
        const dropdown = document.getElementById('jasaDropdown');
        if(searchInput) searchInput.value = '';
        if(dropdown) dropdown.classList.add('hidden');

    } catch (error) {
        console.error("Error submit jasa:", error);
        alert(`Gagal menyimpan jasa. Error: ${error.message}.`);
    } finally {
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    }
});

// --- FUNGSI UTILITY: Penyimpanan Detail Pelanggan ---
function saveCustomerDetails() {
    const customerDetails = JSON.parse(localStorage.getItem('customerDetails')) || {};
    
    // Pastikan semua ID input di detail.html sudah sesuai
    const nameInput = document.getElementById('customerName');
    const plateInput = document.getElementById('customerPlate');
    const phoneInput = document.getElementById('customerPhone');
    const noteInput = document.getElementById('customerNote');
    
    // Simpan nilai ke objek customerDetails
    if (nameInput) customerDetails.name = nameInput.value;
    if (plateInput) customerDetails.plate = plateInput.value;
    if (phoneInput) customerDetails.phone = phoneInput.value;
    if (noteInput) customerDetails.note = noteInput.value;
    if (phoneInput) {
        // Clean phone number: remove non-numeric characters and ensure it starts with '62'
        let cleanedPhone = phoneInput.value.replace(/\D/g, ''); // Remove all non-digits
        if (cleanedPhone.startsWith('0')) {
            cleanedPhone = '62' + cleanedPhone.substring(1); // Replace leading '0' with '62'
        } else if (!cleanedPhone.startsWith('62') && cleanedPhone.length > 0) {
            cleanedPhone = '62' + cleanedPhone; // Prepend '62' if not already present and not empty
        }
        customerDetails.phone = cleanedPhone;
    }

    localStorage.setItem('customerDetails', JSON.stringify(customerDetails));
}

// --- INVOICE PAGE ---
// --- services.js (Fungsi initInvoicePage) ---

function initInvoicePage() {
    const invoiceItems = document.getElementById('invoiceItems');
    if (!invoiceItems) return;

    // 1. AMBIL SEMUA DATA DARI LOCALSTORAGE
    const cartData = JSON.parse(localStorage.getItem('currentServiceInvoice') || '[]');
    const carData = JSON.parse(localStorage.getItem('currentCar') || 'null') || {}; // Ensure it's an object, even if empty
    const customerData = JSON.parse(localStorage.getItem('customerDetails') || '{}'); 

    // 2. SET METADATA INVOICE
    document.getElementById('invoiceNumber').innerText = `INV-${Date.now().toString().slice(-6)}`;
    
    const dateOptions = { year: 'numeric', month: 'long', day: 'numeric' };
    document.getElementById('invoiceDate').innerText = new Date().toLocaleDateString('id-ID', dateOptions);

    // 3. TAMPILKAN DETAIL PELANGGAN
    document.getElementById('customerNameInv').innerText = customerData.name || '-';
    document.getElementById('customerPlateInv').innerText = customerData.plate || '-';
    document.getElementById('customerPhoneInv').innerText = customerData.phone || '-';
    document.getElementById('customerNoteInv').innerText = customerData.note || '-';
    
    // 4. RESET & RENDER ITEM TABEL
    let subtotal = 0;
    invoiceItems.innerHTML = '';

    if (cartData.length === 0) {
        invoiceItems.innerHTML = `<tr><td colspan="5" class="text-center py-4 text-gray-500">Tidak ada item.</td></tr>`;
    }

    cartData.forEach(item => {
        let itemTotal = 0;
        let qtyDisplay = '';
        let priceUnitDisplay = '';
        const unitPrice = item.price || 0;     
        const lcRate = item.lc_per_hour || 0; 

        
        // --- LOGIKA PERHITUNGAN JASA (Industrial Minutes / Basis 100) ---
        if (item.type === 'service') {
            const qty = item.quantity || 100; 
            
            // Perhitungan: (LC Rate / 100) * Qty Menit
            itemTotal = (lcRate / 100) * qty; 
            
            priceUnitDisplay = `Rp ${lcRate.toLocaleString('id-ID')}/100 mnt`; 
            // Konversi Menit (100) ke Jam Desimal (1.00) untuk tampilan Qty
            qtyDisplay = `${(qty / 100).toFixed(2)} Jam`; 
        } 
        
        // --- LOGIKA PERHITUNGAN SPAREPART ---
        else {
            const qty = item.quantity || 1;
            itemTotal = unitPrice * qty;
            
            priceUnitDisplay = `Rp ${unitPrice.toLocaleString('id-ID')}/pcs`; // Display harga per pcs
            qtyDisplay = `${qty} Pcs`;
        }

        subtotal += itemTotal;

        const tr = document.createElement('tr');
        tr.className = "border-b hover:bg-gray-50";
        tr.innerHTML = `
            <td class="p-3">
                <div class="font-medium text-gray-800">${item.name}</div>
                <div class="text-xs text-gray-500">${item.code}</div>
            </td>
            <td class="p-3 text-gray-600">${carData.model || '-'}</td>
            <td class="p-3 text-right text-sm">${priceUnitDisplay}</td>
            <td class="p-3 text-center">${qtyDisplay}</td>
            <td class="p-3 text-right font-bold">Rp ${Math.round(itemTotal).toLocaleString('id-ID')}</td>
        `;
        invoiceItems.appendChild(tr);
    });

    // --- KALKULASI TOTAL AKHIR ---
    const ppn = subtotal * 0.11;
    const grandTotal = subtotal + ppn;

    document.getElementById('invoiceSubtotal').innerText = `Rp ${Math.round(subtotal).toLocaleString('id-ID')}`;
    document.getElementById('invoicePPN').innerText = `Rp ${Math.round(ppn).toLocaleString('id-ID')}`;
    document.getElementById('invoiceTotal').innerText = `Rp ${Math.round(grandTotal).toLocaleString('id-ID')}`;

    // 5. SIAPKAN PAYLOAD UNTUK WHATSAPP & PASANG LISTENER
    const payloadData = {
        customer: customerData,
        car: carData,
        items: cartData,
        totals: {
            subtotal: subtotal,
            grand_total: grandTotal,
            ppn: ppn,
            discount: 0
        }
    };

    const whatsappBtn = document.getElementById('whatsappBtn');
    if (whatsappBtn) {
        // Memanggil fungsi pengiriman PDF yang ada di services.js
        whatsappBtn.onclick = () => sendInvoiceAsPdf(payloadData); 
    }

    const printBtn = document.getElementById('printBtn');
    if(printBtn) printBtn.onclick = () => window.print();
}

// --- APP INIT ---
document.addEventListener('DOMContentLoaded', async () => {
    // Muat Cart dari Storage
    try {
        cart = JSON.parse(localStorage.getItem('currentServiceInvoice') || '[]');
    } catch (e) { cart = []; }
    
    const path = window.location.pathname;

    // --- LOGIKA UTAMA PER JALUR HALAMAN ---
    if (path.includes('detail.html')) {
        await initDetailPageUI();
        
        // Pasang Listener Kalkulasi Real-time Modal
        const durationInput = document.getElementById('newJasaDuration');
        const laborChargeInput = document.getElementById('newJasaLaborCharge');
        
        if (durationInput && laborChargeInput) {
            // Pasang event listener untuk memicu update kalkulasi setiap ada ketikan
            durationInput.addEventListener('input', updateCalculatedRateDisplay);
            laborChargeInput.addEventListener('input', updateCalculatedRateDisplay);
            
            // Panggil sekali untuk menampilkan default Rp 0
            setTimeout(updateCalculatedRateDisplay, 1000); 
        }

    } else if (path.includes('invoice.html')) {
        initInvoicePage();
    } else {
        // Bagian ini mencakup services.html dan root path default (Halaman Pemilihan Mobil)
        
        // 1. Render kartu mobil awal
        renderCarCards();
        
        // 2. Pasang Listener Search Bar (FIX FILTER)
        // Listener ini akan memanggil filterCarCards() yang sudah didefinisikan
        const searchInput = document.getElementById('searchBar');
        if (searchInput) {
            searchInput.addEventListener('input', filterCarCards); 
        }
    }
});

// --- FUNGSI PENGIRIM PDF KE WHATSAPP ---
// (Ini harus diletakkan di bagian atas/utility services.js)

async function sendInvoiceAsPdf(payload) {

    const token = localStorage.getItem('authToken');
    const GENERATE_API_URL = `${API_BASE_URL}/api/invoice/send_whatsapp`;

    const whatsappBtn = document.getElementById('whatsappBtn');
    const originalContent = whatsappBtn.innerHTML;

    // =============================
    // PAYLOAD SESUAI BACKEND
    // =============================
    const fixedPayload = {
        customer: {
            name: payload.customer.name,
            phone: payload.customer.phone,
            plate: payload.customer.plate || "-",
            note: payload.customer.note || "-"
        },
        car: {
            model: payload.car.model
        },
        items: payload.items.map(item => ({
            code: item.code || "-",
            name: item.name,
            type: item.type,                 // "service" / "sparepart"
            quantity: item.quantity,
            lc_per_hour: item.lc_per_hour || 0,
            price: item.price || 0
        })),
        totals: {
            subtotal: payload.totals.subtotal,
            ppn: payload.totals.ppn,
            grand_total: payload.totals.grand_total,
            discount: payload.totals.discount || 0
        }
    };

    console.log("📦 PAYLOAD FINAL (VALID):", fixedPayload);

    // =============================
    // VALIDASI MINIMAL
    // =============================
    if (!fixedPayload.customer.phone) {
        alert("Nomor WhatsApp tidak valid");
        return;
    }

    whatsappBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Mengirim...';
    whatsappBtn.disabled = true;

    try {
        const response = await fetch(GENERATE_API_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...(token && { "Authorization": `Bearer ${token}` })
            },
            body: JSON.stringify(fixedPayload)
        });

        if (!response.ok) {
            const err = await response.json();
            console.error("❌ BACKEND ERROR:", err);
            throw new Error("Validasi backend gagal (422)");
        }

        const result = await response.json();
        console.log("📨 WhatsApp API Response:", result);

        alert("✅ Invoice PDF berhasil dikirim ke WhatsApp!");

    } catch (err) {
        console.error("❌ Error sending PDF:", err);
        alert("❌ Gagal mengirim invoice. Cek console.");
    } finally {
        whatsappBtn.innerHTML = originalContent;
        whatsappBtn.disabled = false;
    }
}
