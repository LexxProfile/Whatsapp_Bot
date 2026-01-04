// /root/Whatsapp_Bot/frontend-build/sparepart.js

document.addEventListener('DOMContentLoaded', async function() {
    const API_BASE_URL = ''; // Menggunakan global API_BASE_URL
    const listContainer = document.getElementById('listContainer');
    const searchByNameInput = document.getElementById('searchByName');
    const searchByNumberInput = document.getElementById('searchByNumber');

    let allSpareparts = []; // To store all spare parts fetched from the API

    // Function to format currency
    function formatRupiah(number) {
        return new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', minimumFractionDigits: 0 }).format(number);
    }

    // Function to fetch spare parts from the API
    async function fetchSpareparts() {
        listContainer.innerHTML = `<div class="text-center py-4 text-gray-500"><i class="fas fa-spinner fa-spin mr-2"></i> Memuat daftar sparepart...</div>`;
        try {
            const token = localStorage.getItem('authToken');
            if (!token) {
                listContainer.innerHTML = `<div class="text-center py-4 text-red-500">Anda harus login untuk melihat daftar sparepart.</div>`;
                return;
            }

            const response = await fetch(`${API_BASE_URL}/api/spareparts`, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Gagal memuat daftar sparepart.');
            }

            const data = await response.json();
            allSpareparts = data; // Store all fetched spare parts
            renderSpareparts(allSpareparts); // Render all spare parts initially

        } catch (error) {
            console.error('Error fetching spare parts:', error);
            listContainer.innerHTML = `<div class="text-center py-4 text-red-500">Error: ${error.message}</div>`;
        }
    }

    // Function to render spare parts into the container
    function renderSpareparts(sparepartsToRender) {
        listContainer.innerHTML = ''; // Clear previous content

        if (sparepartsToRender.length === 0) {
            listContainer.innerHTML = `<div class="text-center py-4 text-gray-500"><i class="fas fa-box-open mr-2"></i> Tidak ada sparepart yang ditemukan.</div>`;
            return;
        }

        sparepartsToRender.forEach(sparepart => {
            const sparepartCard = document.createElement('div');
            sparepartCard.className = 'service-card'; // Reusing service-card style
            sparepartCard.innerHTML = ` 
                <img src="${sparepart.image_url || 'https://via.placeholder.com/150?text=No+Image'}" alt="${sparepart.part_name}" class="mb-3">
                <div class="service-title">${sparepart.part_name}</div>
                <p class="text-sm text-gray-600">No. Part: ${sparepart.part_number}</p>
                <p class="text-md font-bold text-blue-600 mt-2">${formatRupiah(sparepart.price)}</p>
            `;
            listContainer.appendChild(sparepartCard);
        });
    }

    // Function to filter spare parts based on search input
    function filterSpareparts() {
        const nameQuery = searchByNameInput.value.toLowerCase();
        const numberQuery = searchByNumberInput.value.toLowerCase();

        const filtered = allSpareparts.filter(sparepart => {
            const matchesName = sparepart.part_name.toLowerCase().includes(nameQuery);
            const matchesNumber = sparepart.part_number.toLowerCase().includes(numberQuery);
            return matchesName && matchesNumber;
        });

        renderSpareparts(filtered);
    }

    // Add event listeners for search inputs
    searchByNameInput.addEventListener('input', filterSpareparts);
    searchByNumberInput.addEventListener('input', filterSpareparts);

    // Initial fetch of spare parts when the page loads
    fetchSpareparts();
});