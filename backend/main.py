import os
import bcrypt
import jwt
from typing import Optional
from datetime import datetime, timedelta, timezone # Import timezone
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer # Tetap pakai ini untuk dependensi
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import mysql.connector
from dotenv import load_dotenv

# Muat variabel environment (jika ada file .env di folder backend/)
load_dotenv()

# --- Konfigurasi ---
app = FastAPI(title="Chatbot Backend API", description="API untuk mengelola user dan riwayat chat.")

# --- Konfigurasi CORS ---
origins = [
    "http://localhost:3000", # Alamat frontend Anda
    # Tambahkan origin production Anda nanti jika perlu
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ambil konfigurasi dari environment variables Docker Compose
DATABASE_HOST = os.getenv("DATABASE_HOST", "db")
DATABASE_USER = os.getenv("DATABASE_USER", "user_n8n")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD", "root") # Ingat ganti ini!
DATABASE_NAME = os.getenv("DATABASE_NAME", "chatbot_history")
# Pastikan JWT_SECRET kuat dan diambil dari environment variable di production!
JWT_SECRET = os.getenv("JWT_SECRET", "GantiDenganRahasiaJWTYangKuatDanPanjang")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 # Token berlaku 1 jam

# --- Model Data Pydantic ---
class UserCreate(BaseModel):
    phone_number: str
    password: str

class UserLogin(BaseModel):
    phone_number: str # Frontend akan mengirim ini sebagai phone_number
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    phone_number: Optional[str] = None

class OrderCreate(BaseModel):
    item_name: str
    quantity: int
    # Harga dan total bisa ditambahkan di sini jika perlu
    # item_price: float

# --- Koneksi Database ---
def get_db_connection():
    try:
        # Menambahkan connection_timeout
        conn = mysql.connector.connect(
            host=DATABASE_HOST,
            user=DATABASE_USER,
            password=DATABASE_PASSWORD,
            database=DATABASE_NAME,
            connection_timeout=10 # Timeout setelah 10 detik jika gagal konek
        )
        # Periksa koneksi
        if conn.is_connected():
             print("Koneksi database berhasil.")
             return conn
        else:
             print("Koneksi database GAGAL.")
             raise HTTPException(status_code=503, detail="Tidak bisa terhubung ke database.")

    except mysql.connector.Error as err:
        print(f"Error koneksi database: {err}")
        # Bedakan error spesifik jika perlu
        if err.errno == mysql.connector.errorcode.ER_ACCESS_DENIED_ERROR:
             raise HTTPException(status_code=401, detail=f"Akses database ditolak untuk user '{DATABASE_USER}'")
        elif err.errno == mysql.connector.errorcode.ER_BAD_DB_ERROR:
             raise HTTPException(status_code=404, detail=f"Database '{DATABASE_NAME}' tidak ditemukan")
        else:
             raise HTTPException(status_code=500, detail=f"Error database tidak dikenal: {err}")
    except Exception as e:
        print(f"Error tidak terduga saat koneksi DB: {e}")
        raise HTTPException(status_code=500, detail="Error server internal.")


# --- Fungsi Utilitas Keamanan ---
def hash_password(password: str) -> str:
    """Meng-hash password menggunakan bcrypt."""
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(pwd_bytes, salt)
    return hashed_password.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Memverifikasi password plain dengan hash."""
    password_byte_enc = plain_password.encode('utf-8')
    hashed_password_byte_enc = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_byte_enc, hashed_password_byte_enc)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Membuat token JWT."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Default expiry time
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt

# Skema OAuth2 untuk dependensi (meskipun login tidak pakai form)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """Mendekode token JWT dan mengembalikan nomor telepon (subject)."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        phone_number: Optional[str] = payload.get("sub")
        if phone_number is None:
            raise credentials_exception
        # Di sini Anda bisa menambahkan pengecekan user ke DB jika perlu
        return phone_number
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except jwt.PyJWTError as e:
         print(f"JWT Error: {e}") # Log error JWT
         raise credentials_exception
    except Exception as e:
        print(f"Unexpected error in get_current_user: {e}") # Log error tak terduga
        raise credentials_exception

# --- Endpoints API ---

@app.get("/")
def read_root():
    return {"message": "Selamat datang di Backend API Chatbot!"}

@app.post("/api/register", status_code=status.HTTP_201_CREATED)
async def register_user(user: UserCreate):
    conn = None
    cursor = None
    try:
        hashed_pw = hash_password(user.password)
        conn = get_db_connection()
        cursor = conn.cursor()

        # Cek duplikasi
        cursor.execute("SELECT phone_number FROM users WHERE phone_number = %s", (user.phone_number,))
        if cursor.fetchone():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nomor telepon sudah terdaftar")

        # Insert user baru
        cursor.execute(
            "INSERT INTO users (phone_number, password_hash) VALUES (%s, %s)",
            (user.phone_number, hashed_pw)
        )
        conn.commit()
        return {"message": "Registrasi berhasil"}

    except mysql.connector.Error as err:
        print(f"Register DB Error: {err}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Terjadi kesalahan pada database saat registrasi.")
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        print(f"Register Unexpected Error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Terjadi kesalahan tidak terduga.")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

# --- Endpoint Login (Menerima JSON, bukan Form) ---
@app.post("/api/login", response_model=Token)
async def login_for_access_token(user_credentials: UserLogin): # Menggunakan model Pydantic UserLogin
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT phone_number, password_hash FROM users WHERE phone_number = %s", (user_credentials.phone_number,))
        user_in_db = cursor.fetchone()

        # Verifikasi user dan password
        is_password_correct = False
        if user_in_db:
            is_password_correct = verify_password(user_credentials.password, user_in_db['password_hash'])

        # Jika user tidak ditemukan atau password salah
        if not user_in_db or not is_password_correct:
            # Alih-alih 401, kita bisa kirim 400 atau 401, tapi pastikan frontend bisa handle
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nomor telepon atau password salah")

        # Buat token JWT
        access_token = create_access_token(data={"sub": user_in_db['phone_number']})

        return {"access_token": access_token, "token_type": "bearer"} # Ini adalah respons sukses

    except mysql.connector.Error as err:
        print(f"Login DB Error: {err}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Terjadi kesalahan pada database saat login.")
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        print(f"Login Unexpected Error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Terjadi kesalahan tidak terduga.")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()


# --- Endpoint History (Memerlukan Otentikasi) ---
@app.get("/api/chat-history")
async def read_chat_history(current_user_phone: str = Depends(get_current_user)):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # [FIXED] Membuat query lebih fleksibel untuk menangani format nomor telepon yang berbeda
        # (misal: 0812... vs 62812...)
        phone_with_62 = current_user_phone
        if current_user_phone.startswith('0'):
            phone_with_62 = '62' + current_user_phone[1:]
        
        phone_with_0 = current_user_phone
        if current_user_phone.startswith('62'):
            phone_with_0 = '0' + current_user_phone[2:]
            
        # Query sekarang mencari semua variasi format nomor telepon
        cursor.execute(
            "SELECT id, waktu, chat_recipient, response_agent FROM chat_history WHERE recipient_id IN (%s, %s, %s, CONCAT(%s, '@s.whatsapp.net'), CONCAT(%s, '@s.whatsapp.net')) ORDER BY waktu DESC LIMIT 50",
            (current_user_phone, phone_with_62, phone_with_0, phone_with_62, phone_with_0)
        )
        history_from_db = cursor.fetchall()

        # "Menerjemahkan" nama kolom dari database ke format yang diharapkan frontend
        formatted_history = []
        for row in history_from_db:
            formatted_row = {
                "id": row.get("id"),
                "user_message": row.get("chat_recipient"), # chat_recipient -> user_message
                "bot_response": row.get("response_agent"), # response_agent -> bot_response
                "waktu": row.get("waktu").isoformat() if row.get("waktu") and isinstance(row.get("waktu"), datetime) else None
            }
            formatted_history.append(formatted_row)


        return formatted_history

    except mysql.connector.Error as err:
        print(f"History DB Error: {err}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal mengambil riwayat chat.")
    except HTTPException as http_err:
        raise http_err # Lemparkan error otentikasi
    except Exception as e:
        print(f"History Unexpected Error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Terjadi kesalahan tidak terduga.")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

# --- Endpoint untuk MEMBUAT Orderan Baru (Memerlukan Otentikasi) --- [FIXED]
@app.post("/api/orders", status_code=status.HTTP_201_CREATED)
async def create_order(order_data: OrderCreate, current_user_phone: str = Depends(get_current_user)):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Menggabungkan item dan kuantitas menjadi satu string untuk kolom 'items'
        items_description = f"{order_data.item_name} (Qty: {order_data.quantity})"

        # Query untuk memasukkan data ke tabel 'orders'
        # ASUMSI: Nama pelanggan dan alamat bisa diisi nanti atau diambil dari profil user
        cursor.execute(
            """
            INSERT INTO orders (user_phone_number, customer_name, address, items, status, waktu)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                current_user_phone,
                "From Chat History", # Placeholder untuk nama pelanggan
                "Alamat belum diisi", # Placeholder untuk alamat
                items_description,
                "Baru", # Status default
                datetime.now(timezone(timedelta(hours=7))) # Waktu saat ini (WIB)
            )
        )
        conn.commit()
        return {"message": "Order berhasil ditambahkan"}

    except mysql.connector.Error as err:
        print(f"Create Order DB Error: {err}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Terjadi kesalahan pada database saat membuat orderan.")
    except HTTPException as http_err:
        # Melemparkan kembali error otentikasi dari get_current_user
        raise http_err
    except Exception as e:
        print(f"Create Order Unexpected Error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Terjadi kesalahan tidak terduga saat membuat orderan.")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

# --- Endpoint untuk MEMBACA Daftar Orderan (Memerlukan Otentikasi) --- [FIXED AGAIN]
@app.get("/api/orders/list") # Pastikan URL ini unik
async def read_orders(current_user_phone: str = Depends(get_current_user)):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # [FIXED] Membuat query lebih fleksibel untuk menangani format nomor telepon yang berbeda
        # (misal: 0812... vs 62812...)
        # 1. Buat versi '62' dari nomor telepon jika dimulai dengan '0'
        phone_with_62 = current_user_phone
        if current_user_phone.startswith('0'):
            phone_with_62 = '62' + current_user_phone[1:]
        
        # 2. Buat versi '0' dari nomor telepon jika dimulai dengan '62'
        phone_with_0 = current_user_phone
        if current_user_phone.startswith('62'):
            phone_with_0 = '0' + current_user_phone[2:]
        
        cursor.execute(
            "SELECT id, waktu, customer_name, address, items, status FROM orders WHERE user_phone_number IN (%s, %s, %s) ORDER BY waktu DESC LIMIT 50",
            (current_user_phone, phone_with_62, phone_with_0)
        )
        orders_from_db = cursor.fetchall()

        # Format waktu ke ISO string agar konsisten
        for order in orders_from_db:
            if order.get('waktu') and isinstance(order.get('waktu'), datetime):
                order['waktu'] = order['waktu'].isoformat()

        return orders_from_db

    except mysql.connector.Error as err:
        print(f"Orders DB Error: {err}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal mengambil daftar orderan.")
    except Exception as e:
        print(f"Orders Unexpected Error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Terjadi kesalahan tidak terduga saat mengambil orderan.")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()