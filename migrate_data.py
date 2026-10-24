import os
import glob
import json
import psycopg2

def run_migration():
    files = glob.glob('/app/data/tthc/**/*.json', recursive=True)
    if not files:
        files = glob.glob('/app/data/**/*.json', recursive=True)

    print(f"📂 Đã tìm thấy {len(files)} file dữ liệu thủ tục!")

    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'postgres'),
        database=os.getenv('POSTGRES_DB', 'luatganban_db'),
        user=os.getenv('POSTGRES_USER', 'lgb_admin'),
        password=os.getenv('POSTGRES_PASSWORD', 'lgb_password_2026'),
        port=os.getenv('DB_PORT', '5432')
    )
    cur = conn.cursor()

    count = 0
    for fpath in files:
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                item = json.load(f)
                
                if isinstance(item, dict):
                    ma_dir = os.path.basename(os.path.dirname(fpath))
                    ma = item.get('ma_thu_tuc') or item.get('code') or item.get('id') or ma_dir
                    ten = item.get('ten_thu_tuc') or item.get('tieu_de') or item.get('ten') or item.get('title') or f"Thủ tục {ma}"
                    nd_vi = item.get('noi_dung_tieng_viet') or item.get('noi_dung') or item.get('content') or ''
                    if isinstance(nd_vi, (list, dict)):
                        nd_vi = json.dumps(nd_vi, ensure_ascii=False)
                        
                    nd_hm = item.get('noi_dung_tieng_hmong') or item.get('noi_dung_hmong') or item.get('hmong') or ''
                    if isinstance(nd_hm, (list, dict)):
                        nd_hm = json.dumps(nd_hm, ensure_ascii=False)
                        
                    sdt = item.get('sdt_can_bo') or item.get('sdt') or ''
                    
                    if ma and (ten or nd_vi):
                        cur.execute("""
                            INSERT INTO thu_tuc_hanh_chinh (ma_thu_tuc, ten_thu_tuc, noi_dung_tieng_viet, noi_dung_tieng_hmong, sdt_can_bo, trang_thai, nguoi_tao)
                            VALUES (%s, %s, %s, %s, %s, 'da_duyet', 'system_migration')
                            ON CONFLICT (ma_thu_tuc) DO UPDATE 
                            SET ten_thu_tuc = EXCLUDED.ten_thu_tuc,
                                noi_dung_tieng_viet = EXCLUDED.noi_dung_tieng_viet,
                                noi_dung_tieng_hmong = EXCLUDED.noi_dung_tieng_hmong,
                                sdt_can_bo = EXCLUDED.sdt_can_bo,
                                trang_thai = 'da_duyet';
                        """, (ma, ten, nd_vi, nd_hm, sdt))
                        count += 1
                elif isinstance(item, list):
                    for idx, row in enumerate(item, 1):
                        if isinstance(row, dict):
                            ma = row.get('ma_thu_tuc') or row.get('id') or f"TT-{idx:04d}"
                            ten = row.get('ten_thu_tuc') or row.get('tieu_de') or row.get('ten') or 'Thủ tục hành chính'
                            vi = row.get('noi_dung_tieng_viet') or row.get('noi_dung') or ''
                            if isinstance(vi, (list, dict)): vi = json.dumps(vi, ensure_ascii=False)
                            hm = row.get('noi_dung_tieng_hmong') or row.get('noi_dung_hmong') or ''
                            if isinstance(hm, (list, dict)): hm = json.dumps(hm, ensure_ascii=False)
                            sdt = row.get('sdt_can_bo') or row.get('sdt') or ''
                            
                            cur.execute("""
                                INSERT INTO thu_tuc_hanh_chinh (ma_thu_tuc, ten_thu_tuc, noi_dung_tieng_viet, noi_dung_tieng_hmong, sdt_can_bo, trang_thai, nguoi_tao)
                                VALUES (%s, %s, %s, %s, %s, 'da_duyet', 'system_migration')
                                ON CONFLICT (ma_thu_tuc) DO UPDATE 
                                SET ten_thu_tuc = EXCLUDED.ten_thu_tuc,
                                    noi_dung_tieng_viet = EXCLUDED.noi_dung_tieng_viet,
                                    noi_dung_tieng_hmong = EXCLUDED.noi_dung_tieng_hmong,
                                    sdt_can_bo = EXCLUDED.sdt_can_bo,
                                    trang_thai = 'da_duyet';
                            """, (ma, ten, vi, hm, sdt))
                            count += 1
        except Exception as e:
            pass

    conn.commit()
    print(f"🎉 MIGRATION THÀNH CÔNG! Đã nạp {count} bản ghi thủ tục vào PostgreSQL.")
    cur.close()
    conn.close()

if __name__ == '__main__':
    run_migration()
