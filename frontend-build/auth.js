document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    const errorMessage = document.getElementById('errorMessage');
    const successMessage = document.getElementById('successMessage');

    // URL API (Relatif)
    const API_BASE_URL = ''; 

    // --- FUNGSI BANTUAN: NORMALISASI NOMOR TELEPON ---
    // Mengubah format '08...' menjadi '628...'
    // Jika sudah '62...', biarkan apa adanya.
    // Juga membersihkan karakter non-angka (spasi, -, dll)
    function normalizePhoneNumber(phone) {
        // 1. Hapus karakter selain angka
        let cleanPhone = phone.replace(/\D/g, '');

        // 2. Cek awalan
        if (cleanPhone.startsWith('0')) {
            // Ganti '0' di depan dengan '62'
            cleanPhone = '62' + cleanPhone.substring(1);
        }
        // Jika sudah dimulai dengan '62', biarkan saja
        
        return cleanPhone;
    }

    // --- LOGIN HANDLER ---
    if (loginForm) {
        loginForm.addEventListener('submit', async function(event) {
            event.preventDefault(); 
            hideMessages();

            let phone = document.getElementById('phone').value;
            const password = document.getElementById('password').value;

            // [NEW] Normalisasi nomor telepon sebelum dikirim
            phone = normalizePhoneNumber(phone);
            console.log("Nomor HP dinormalisasi (Login):", phone); // Debugging

            try {
                const response = await fetch(`${API_BASE_URL}/api/login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ phone_number: phone, password: password })
                });

                if (!response.ok) {
                    try {
                        const errorData = await response.json();
                        throw new Error(errorData.detail || `Login gagal (Status: ${response.status})`);
                    } catch (e) {
                        // Jika error saat parsing JSON, lemparkan error asli jika ada pesan
                        throw new Error(e.message || `Login gagal. Server merespon dengan status: ${response.status}`);
                    }
                }

                const data = await response.json();
                if (data.access_token) {
                    localStorage.setItem('authToken', data.access_token);
                    window.location.href = 'index.html';
                } else {
                     showError('Token tidak diterima dari server.');
                }

            } catch (error) {
                console.error('Login Error:', error);
                showError(error.message);
            }
        });
    }

    // --- REGISTER HANDLER ---
    if (registerForm) {
        registerForm.addEventListener('submit', async function(event) {
            event.preventDefault();
            hideMessages();

            let phone = document.getElementById('phone').value;
            const password = document.getElementById('password').value;
            const confirmPassword = document.getElementById('confirmPassword').value;

            if (password !== confirmPassword) {
                showError('Password dan Konfirmasi Password tidak cocok.');
                return;
            }

            // [NEW] Normalisasi nomor telepon sebelum dikirim
            phone = normalizePhoneNumber(phone);
            console.log("Nomor HP dinormalisasi (Register):", phone); // Debugging

            try {
                const response = await fetch(`${API_BASE_URL}/api/register`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ phone_number: phone, password: password })
                });

                if (!response.ok) {
                    try {
                        const errorData = await response.json();
                        throw new Error(errorData.detail || `Registrasi gagal (Status: ${response.status})`);
                    } catch (e) {
                         throw new Error(e.message || `Registrasi gagal. Server merespon dengan status: ${response.status}`);
                    }
                }

                // Jika sukses (201 Created), biasanya tidak ada body atau body minimal
                // Tapi kita coba baca json untuk memastikan
                try {
                     await response.json(); 
                } catch (e) { /* Abaikan jika body kosong */ }

                showSuccess('Registrasi berhasil! Silakan login.');
                registerForm.reset(); 

            } catch (error) {
                console.error('Register Error:', error);
                showError(error.message);
            }
        });
    }

    // --- Fungsi Bantuan UI ---
    function showError(message) {
        if (errorMessage) {
            errorMessage.textContent = message;
            errorMessage.classList.remove('hidden');
        }
    }

     function showSuccess(message) {
        if (successMessage) {
            successMessage.textContent = message;
            successMessage.classList.remove('hidden');
        }
    }

    function hideMessages() {
        if (errorMessage) errorMessage.classList.add('hidden');
        if (successMessage) successMessage.classList.add('hidden');
    }
});