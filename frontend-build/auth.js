document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    const errorMessage = document.getElementById('errorMessage');
    const successMessage = document.getElementById('successMessage');

    // --- BASE URL API BACKEND ANDA ---
    // Pastikan backend Anda berjalan dan bisa diakses
    // Membuat URL API dinamis. Ini akan berfungsi di localhost dan saat diakses dari luar.
    const API_BASE_URL = `${window.location.protocol}//${window.location.hostname}:8000`;

    // --- LOGIN HANDLER ---
    if (loginForm) {
        loginForm.addEventListener('submit', async function(event) {
            event.preventDefault(); // Mencegah reload halaman
            hideMessages();

            const phone = document.getElementById('phone').value;
            const password = document.getElementById('password').value;

            try {
                const response = await fetch(`${API_BASE_URL}/api/login`, {
                    method: 'POST',
                    // Backend sekarang mengharapkan JSON, bukan form-data.
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    // Kirim data sebagai string JSON yang cocok dengan model Pydantic UserLogin di backend
                    body: JSON.stringify({ phone_number: phone, password: password })
                });

                if (!response.ok) {
                    // Coba baca detail error dari body response
                    try {
                        const errorData = await response.json();
                        // Lemparkan error dengan pesan dari backend
                        throw new Error(errorData.detail || `Login gagal (Status: ${response.status})`);
                    } catch (e) {
                        // Jika body bukan JSON atau kosong, lemparkan error umum
                        throw new Error(`Login gagal. Server merespon dengan status: ${response.status}`);
                    }
                }

                const data = await response.json();
                // Login berhasil, simpan token (jika backend mengirim token)
                if (data.access_token) {
                    localStorage.setItem('authToken', data.access_token);
                    window.location.href = 'index.html'; // Arahkan kembali ke halaman utama
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

            const phone = document.getElementById('phone').value;
            const password = document.getElementById('password').value;
            const confirmPassword = document.getElementById('confirmPassword').value;

            if (password !== confirmPassword) {
                showError('Password dan Konfirmasi Password tidak cocok.');
                return;
            }

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
                        throw new Error(`Registrasi gagal. Server merespon dengan status: ${response.status}`);
                    }
                }

                // Baca data hanya jika response.ok
                const data = await response.json();
                // Registrasi berhasil
                showSuccess('Registrasi berhasil! Silakan login.');
                registerForm.reset(); // Kosongkan form

            } catch (error) {
                console.error('Register Error:', error);
                showError(error.message);
            }
        });
    }

    // --- Fungsi Bantuan Tampilkan Pesan ---
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