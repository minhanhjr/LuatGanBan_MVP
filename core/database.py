import os
import psycopg2
from psycopg2.extras import RealDictCursor

DB_HOST = os.getenv("DB_HOST", "postgres")
DB_NAME = os.getenv("POSTGRES_DB", "luatganban_db")
DB_USER = os.getenv("POSTGRES_USER", "lgb_admin")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "lgb_password_2026")
DB_PORT = os.getenv("DB_PORT", "5432")

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )

# ==============================================================================
# 1. TẦNG NGƯỜI DÂN: CHẶN TRIỆT ĐỂ BÀI CHƯA DUYỆT TỪ CÂU LỆNH SQL (SRS 9.55)
# ==============================================================================
def lay_danh_sach_thu_tuc_cho_nguoi_dan(tu_khoa=""):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    sql = """
        SELECT ma_thu_tuc, ten_thu_tuc, noi_dung_tieng_viet, noi_dung_tieng_hmong, sdt_can_bo
        FROM thu_tuc_hanh_chinh
        WHERE trang_thai = 'da_duyet'
    """
    params = []
    if tu_khoa:
        sql += " AND (ten_thu_tuc ILIKE %s OR noi_dung_tieng_viet ILIKE %s)"
        params.extend([f"%{tu_khoa}%", f"%{tu_khoa}%"])
        
    sql += " ORDER BY updated_at DESC;"
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# ==============================================================================
# 2. TẦNG CÁN BỘ: LƯU VĨNH VIỄN VÀO POSTGRESQL (CT-01, FR-FUT-01)
# ==============================================================================
def can_bo_cap_nhat_thu_tuc(ma_tt, ten_tt, nd_vi, nd_hmong, sdt_can_bo, nguoi_thuc_hien="can_bo"):
    conn = get_db_connection()
    cur = conn.cursor()
    
    sql = """
        INSERT INTO thu_tuc_hanh_chinh 
        (ma_thu_tuc, ten_thu_tuc, noi_dung_tieng_viet, noi_dung_tieng_hmong, sdt_can_bo, trang_thai, nguoi_tao)
        VALUES (%s, %s, %s, %s, %s, 'cho_duyet', %s)
        ON CONFLICT (ma_thu_tuc) DO UPDATE 
        SET ten_thu_tuc = EXCLUDED.ten_thu_tuc,
            noi_dung_tieng_viet = EXCLUDED.noi_dung_tieng_viet,
            noi_dung_tieng_hmong = EXCLUDED.noi_dung_tieng_hmong,
            sdt_can_bo = EXCLUDED.sdt_can_bo,
            trang_thai = 'cho_duyet',
            nguoi_tao = EXCLUDED.nguoi_tao;
    """
    cur.execute(sql, (ma_tt, ten_tt, nd_vi, nd_hmong, sdt_can_bo, nguoi_thuc_hien))
    conn.commit()
    cur.close()
    conn.close()

# ==============================================================================
# 3. TẦNG QUẢN TRỊ VIÊN: BẢNG ĐIỀU KHIỂN PHÊ DUYỆT BÀI
# ==============================================================================
def admin_lay_danh_sach_theo_trang_thai(trang_thai="cho_duyet"):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    sql = """
        SELECT id, ma_thu_tuc, ten_thu_tuc, noi_dung_tieng_viet, noi_dung_tieng_hmong, 
               sdt_can_bo, trang_thai, nguoi_tao, updated_at
        FROM thu_tuc_hanh_chinh
        WHERE trang_thai = %s::trang_thai_duyet
        ORDER BY updated_at DESC;
    """
    cur.execute(sql, (trang_thai,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def admin_duyet_hoac_tu_choi(ma_tt, trang_thai_moi, nguoi_duyet="admin", ly_do=""):
    conn = get_db_connection()
    cur = conn.cursor()
    sql = """
        UPDATE thu_tuc_hanh_chinh
        SET trang_thai = %s::trang_thai_duyet, nguoi_duyet = %s, ly_do_tu_choi = %s
        WHERE ma_thu_tuc = %s;
    """
    cur.execute(sql, (trang_thai_moi, nguoi_duyet, ly_do, ma_tt))
    conn.commit()
    cur.close()
    conn.close()
