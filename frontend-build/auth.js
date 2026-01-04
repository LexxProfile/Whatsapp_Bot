document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    const errorMessage = document.getElementById('errorMessage');
    const successMessage = document.getElementById('successMessage');

    const API_BASE_URL = '';

    function normalizePhoneNumber(phone) {
        let cleanPhone = phone.replace(/\D/g, '');
        if (cleanPhone.startsWith('0')) {
            cleanPhone = '62' + cleanPhone.substring(1);
        }
        return cleanPhone;
    }

    /* ================= LOGIN ================= */
    loginForm.addEventListener('submit', async function (e) {
    e.preventDefault();
    hideError();

    let phone = document.getElementById('phoneNumber').value;
    const password = document.getElementById('password').value;

    phone = normalizePhoneNumber(phone);

    if (!/^62\d{9,13}$/.test(phone)) {
        showError('Nomor WhatsApp tidak valid.');
        return;
    }

    // ✅ AMBIL DARI CALLBACK
    if (!window.captchaToken) {
        showError('Silakan selesaikan CAPTCHA terlebih dahulu.');
        return;
    }

    try {
        const res = await fetch(`${API_BASE_URL}/api/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                phone_number: phone,
                password: password,
                captcha_token: window.captchaToken
            })
        });

        const data = await res.json();

        if (!res.ok) {
            throw new Error(data.detail || 'Login gagal.');
        }

        if (data.status === 'pending') {
            showError('Akun Anda masih menunggu persetujuan admin.');
            return;
        }

        if (data.status === 'blocked') {
            showError('Akun Anda diblokir. Hubungi admin.');
            return;
        }

        if (data.access_token) {
            localStorage.setItem('authToken', data.access_token);
            window.location.href = 'index.html';
        } else {
            showError('Token tidak diterima dari server.');
        }

    } catch (err) {
        showError(err.message);
    } finally {
        // 🔁 RESET TOKEN (Turnstile sekali pakai)
        window.captchaToken = null;
    }
});


    /* ================= REGISTER ================= */
    if (registerForm) {
        registerForm.addEventListener('submit', async function(event) {
            event.preventDefault();
            hideMessages();

            let phone = document.getElementById('phoneNumber').value;
            const password = document.getElementById('password').value;
            const confirmPassword = document.getElementById('confirmPassword').value;

            if (password !== confirmPassword) {
                showError('Password dan Konfirmasi Password tidak cocok.');
                return;
            }

            phone = normalizePhoneNumber(phone);

            if (!/^62\d{9,13}$/.test(phone)) {
                showError('Nomor WhatsApp tidak valid.');
                return;
            }

            /* 🔴 INI WAJIB: captchaToken dari register.html */
            if (!window.captchaToken) {
                showError('Silakan selesaikan CAPTCHA terlebih dahulu.');
                return;
            }

            try {
                const response = await fetch(`${API_BASE_URL}/api/register-request`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        phone_number: phone,
                        password: password,
                        captcha_token: window.captchaToken
                    })
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.detail || 'Registrasi gagal.');
                }

                showSuccess(
                    'Permintaan pendaftaran berhasil dikirim. ' +
                    'Menunggu persetujuan admin melalui WhatsApp.'
                );

                registerForm.reset();

            } catch (error) {
                showError(error.message);
            }
        });
    }

    /* ================= UI ================= */
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
