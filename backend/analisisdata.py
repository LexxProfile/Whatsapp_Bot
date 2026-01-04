import pandas as pd
from fastapi import UploadFile, File, HTTPException, APIRouter
from io import BytesIO

router = APIRouter(prefix="/api/report", tags=["Report Analysis"])

# TEMPLATE WAJIB
REQUIRED_COLUMNS = {
    "tanggal",
    "part_number",
    "part_name",
    "kategori_pelanggan",
    "qty",
    "total_penjualan"
}

@router.post("/upload")
async def upload_and_analyze(file: UploadFile = File(...)):
    # ===============================
    # VALIDASI FILE
    # ===============================
    if not file.filename.endswith((".xls", ".xlsx")):
        raise HTTPException(status_code=400, detail="File harus Excel (.xls / .xlsx)")

    try:
        df = pd.read_excel(BytesIO(await file.read()))
    except Exception:
        raise HTTPException(status_code=400, detail="Gagal membaca file Excel")

    # ===============================
    # VALIDASI TEMPLATE
    # ===============================
    if not REQUIRED_COLUMNS.issubset(df.columns):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Template Excel tidak sesuai",
                "required_columns": list(REQUIRED_COLUMNS)
            }
        )

    # ===============================
    # NORMALISASI DATA
    # ===============================
    df["tanggal"] = pd.to_datetime(df["tanggal"])
    df["bulan"] = df["tanggal"].dt.to_period("M").astype(str)
    df["tahun"] = df["tanggal"].dt.year

    # ===============================
    # LEADERBOARD (PALING SERING TERJUAL)
    # ===============================
    leaderboard = (
        df.groupby(["part_number", "part_name"])["qty"]
        .sum()
        .reset_index()
        .sort_values("qty", ascending=False)
        .head(10)
    )

    # ===============================
    # TREND PENJUALAN PER BULAN (TOP PART)
    # ===============================
    top_parts = leaderboard["part_number"].tolist()

    trend = (
        df[df["part_number"].isin(top_parts)]
        .groupby(["tahun", "bulan", "part_number", "part_name"])["total_penjualan"]
        .sum()
        .reset_index()
        .sort_values(["tahun", "bulan"])
    )

    return {
        "leaderboard": leaderboard.to_dict(orient="records"),
        "trend": trend.to_dict(orient="records")
    }
