import streamlit as st
import pandas as pd
import sqlite3  # Kembali menggunakan SQLite lokal
import datetime
import plotly.express as px
import urllib.parse
import hashlib
import io
import os

# ==========================================
# CONFIGURATION & DATABASE INITIALIZATION (LOKAL)
# ==========================================
st.set_page_config(page_title="Sistem Absensi Digital Terpadu (SUPER PREMIUM)", layout="wide", page_icon="💎")

# Fungsi untuk membuka koneksi ke database lokal SQLite
def get_db_connection():
    # File database akan otomatis terbuat di folder yang sama dengan app.py
    conn = sqlite3.connect("absensi_sekolah_premium.db")
    conn.row_factory = sqlite3.Row  # Agar data bisa dibaca seperti kamus (dictionary)
    return conn

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. Tabel Users
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY, 
                    password TEXT, 
                    role TEXT, 
                    nama TEXT,
                    kelas_tugas TEXT)''')
    
    # 2. Tabel Siswa
    c.execute('''CREATE TABLE IF NOT EXISTS siswa (
                    nisn TEXT PRIMARY KEY, nama TEXT, kelas TEXT, nis TEXT, 
                    tempat_lahir TEXT, tanggal_lahir TEXT, agama TEXT, nik TEXT, 
                    alamat TEXT, nama_ayah TEXT, pekerjaan_ayah TEXT, nama_ibu TEXT, 
                    pekerjaan_ibu TEXT, no_wa_orang_tua TEXT)''')
    
    # 3. Tabel Absensi
    c.execute('''CREATE TABLE IF NOT EXISTS absensi (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nisn TEXT, 
                    tanggal TEXT, 
                    status TEXT, 
                    waktu TEXT, 
                    guru_input TEXT,
                    mapel TEXT DEFAULT 'Wali Kelas / Umum',
                    jam_ke TEXT DEFAULT 'Harian',
                    FOREIGN KEY(nisn) REFERENCES siswa(nisn),
                    UNIQUE(nisn, tanggal, mapel, jam_ke))''')
        
    # 4. Tabel Laporan Tindak Lanjut
    c.execute('''CREATE TABLE IF NOT EXISTS laporan_tindak_lanjut (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nisn TEXT, 
                    tanggal TEXT, 
                    catatan TEXT, 
                    status_wa TEXT,
                    FOREIGN KEY(nisn) REFERENCES siswa(nisn))''')
                    
    # 5. Tabel Aduan Curhat
    c.execute('''CREATE TABLE IF NOT EXISTS aduan_curhat (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tanggal TEXT,
                    guru_pengirim TEXT,
                    jenis_aduan TEXT,
                    isi_curhat TEXT,
                    status_tindak_lanjut TEXT DEFAULT 'Belum Dibaca',
                    catatan_kepsek TEXT DEFAULT '-')''')
                    
    # 6. Tabel Biodata Sekolah
    c.execute('''CREATE TABLE IF NOT EXISTS biodata_sekolah (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    nama_kab_kota TEXT DEFAULT 'PEMERINTAH KABUPATEN / KOTA',
                    nama_dinas TEXT DEFAULT 'DINAS PENDIDIKAN DAN KEBUDAYAAN',
                    nama_sekolah TEXT DEFAULT 'SATUAN PENDIDIKAN KELAS PREMIUM',
                    alamat_sekolah TEXT DEFAULT 'Alamat: Jalan Raya Pendidikan No. 1, Kode Pos 12345 Telp. (021) 123456',
                    nama_kepsek TEXT DEFAULT '____________________________',
                    nip_kepsek TEXT DEFAULT '........................................')''')
                    
    # 7. Tabel Status Lisensi Aplikasi
    c.execute('''CREATE TABLE IF NOT EXISTS lisensi_aplikasi (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    status_aktif TEXT DEFAULT 'Trial',
                    tanggal_mulai TEXT,
                    serial_terpasang TEXT DEFAULT '-')''')
    
    # Isi data bawaan instansi jika kosong
    c.execute("SELECT COUNT(*) FROM biodata_sekolah")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO biodata_sekolah (id) VALUES (1)")
        
    # Isi data bawaan lisensi jika kosong
    c.execute("SELECT COUNT(*) FROM lisensi_aplikasi")
    if c.fetchone()[0] == 0:
        hari_ini_str = str(datetime.date.today())
        c.execute("INSERT INTO lisensi_aplikasi (id, status_aktif, tanggal_mulai) VALUES (1, 'Trial', ?)", (hari_ini_str,))
    
    # Cek akun admin bawaan (Password: admin123)
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        hashed_admin = hash_password("admin123")
        c.execute("INSERT INTO users VALUES ('admin', ?, 'Admin', 'Kepala Sekolah', 'SEMUA')", (hashed_admin,))
    
    conn.commit()
    conn.close()

# Jalankan Inisialisasi Tabel di Komputer Lokal
init_db()

# [KODE SISANYA DI BAWAH TETAP SAMA]
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.nama = ""
    st.session_state.kelas_tugas = ""

def get_db_connection():
    conn = sqlite3.connect("absensi_sekolah_premium.db")
    conn.row_factory = sqlite3.Row
    return conn
    
# FITUR BARU: Fungsi Pengunci Sistem & Validasi Serial Key Berdurasi 30 Hari
def proteksi_sistem_lisensi():
    # KUNCI RAHASIA BAPAK (Silakan diganti sesuai selera, jaga kerahasiaannya)
    SERIAL_KEY_RESMI = "HANIN_PREMIUM_REKAP_2026"
    DURASI_TRIAL_HARI = 30
    
    conn = get_db_connection()
    res = conn.execute("SELECT status_aktif, tanggal_mulai, serial_terpasang FROM lisensi_aplikasi WHERE id=1").fetchone()
    conn.close()
    
    status_aktif, tanggal_mulai_str, serial_terpasang = res
    
    # Jika sudah diaktivasi dengan kode yang benar, lolos tanpa batasan waktu
    if status_aktif == "Permanen" and serial_terpasang == SERIAL_KEY_RESMI:
        return
        
    # Hitung sisa hari jika status masih Trial
    tgl_mulai = datetime.datetime.strptime(tanggal_mulai_str, "%Y-%m-%d").date()
    hari_ini = datetime.date.today()
    selisih_hari = (hari_ini - tgl_mulai).days
    sisa_hari = DURASI_TRIAL_HARI - selisih_hari
    
    # Tampilkan info masa trial di pojok atas aplikasi selama masih berlaku
    if sisa_hari >= 0:
        st.sidebar.warning(f"⏳ MODE TRIAL: Sisa {sisa_hari} Hari Lagi.")
    else:
        # Jika waktu habis, kunci total layar aplikasi
        st.markdown("<h2 style='text-align: center; color: #EF4444;'>🚨 MASA UJI COBA (TRIAL) TELAH HABIS</h2>", unsafe_allow_html=True)
        st.markdown(f"""
            <div style="background-color: #FEE2E2; padding: 25px; border-radius: 8px; border: 1px solid #EF4444; color: #000; margin-bottom: 20px;">
                <p style="font-size: 16px; text-align: center;">Masa uji coba gratis 30 hari sistem absensi premium di sekolah ini telah berakhir.</p>
                <p style="font-size: 16px; font-weight: bold; text-align: center;">Untuk mengaktifkan lisensi permanen, silakan hubungi Developer untuk mendapatkan Serial Key resmi:</p>
                <h3 style="color: #4F46E5; text-align: center; margin: 15px 0;">📞 Kontak Developer: 0822-9056-9062 (Papa Hanin)</h3>
            </div>
        """, unsafe_allow_html=True)
        
        # Sediakan kolom input aktivasi langsung di layar kunci
        with st.container():
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                with st.form("aktivasi_kunci_layar"):
                    input_key = st.text_input("🔑 Masukkan Serial Key Aktivasi Resmi:", type="password")
                    if st.form_submit_button("🔥 Aktifkan Aplikasi Selamanya", use_container_width=True):
                        if input_key.strip() == SERIAL_KEY_RESMI:
                            conn = get_db_connection()
                            conn.execute("UPDATE lisensi_aplikasi SET status_aktif='Permanen', serial_terpasang=? WHERE id=1", (SERIAL_KEY_RESMI,))
                            conn.commit()
                            conn.close()
                            st.success("🎉 Sukses! Lisensi Permanen Aktif. Silakan Muat Ulang Halaman.")
                            st.rerun()
                        else:
                            st.error("Serial Key salah! Periksa kembali atau hubungi pengembang.")
        st.stop()

# Jalankan proteksi sistem sebelum masuk halaman login/aplikasi
proteksi_sistem_lisensi()

def ambil_biodata_sekolah():
    conn = get_db_connection()
    res = conn.execute("SELECT nama_kab_kota, nama_dinas, nama_sekolah, alamat_sekolah, nama_kepsek, nip_kepsek FROM biodata_sekolah WHERE id=1").fetchone()
    conn.close()
    return {
        "kab_kota": res[0],
        "dinas": res[1],
        "sekolah": res[2],
        "alamat": res[3],
        "kepsek": res[4],
        "nip_kepsek": res[5]
    }

def kirim_wa_link(no_wa, nama_siswa, kelas, status, konteks_absen="Hari ini"):
    clean_wa = ''.join(filter(str.isdigit, str(no_wa)))
    if clean_wa.startswith('0'):
        clean_wa = '62' + clean_wa[1:]
    
    pesan = f"Assalamualaikum Wr. Wb. Bapak/Ibu Wali Murid, kami menginfokan bahwa *{nama_siswa}* Kelas *{kelas}* *TIDAK HADIR* tanpa keterangan pada {konteks_absen}. Mohon segera hubungi pihak sekolah untuk konfirmasi. Terima kasih."
    pesan_encoded = urllib.parse.quote(pesan)
    return f"https://wa.me/{clean_wa}?text={pesan_encoded}"

def buat_surat_html(nama_siswa, kelas, nisn, alasan, detail_kasus="-"):
    hari_ini_str = datetime.date.today().strftime("%d %B %Y")
    bio = ambil_biodata_sekolah()
    
    html_content = f'''
    <div style="font-family: 'Times New Roman', Times, serif; padding: 20px; color: #000; background: #fff;">
        <div style="text-align: center; border-bottom: 5px double #000; padding-bottom: 10px; margin-bottom: 20px;">
            <h3 style="margin: 0; text-transform: uppercase; font-size: 18px; color: #000;">{bio['kab_kota']}</h3>
            <h2 style="margin: 5px 0; text-transform: uppercase; font-size: 22px; color: #000;">{bio['dinas']}</h2>
            <h1 style="margin: 5px 0; text-transform: uppercase; font-size: 24px; font-weight: bold; color: #000;">{bio['sekolah']}</h1>
            <p style="margin: 0; font-size: 12px; font-style: italic; color: #000;">{bio['alamat']}</p>
        </div>
        
        <table style="width: 100%; font-size: 14px; margin-bottom: 20px; color: #000;">
            <tr>
                <td style="width: 15%; color: #000;">Nomor</td>
                <td style="width: 2%; color: #000;">:</td>
                <td style="width: 48%; color: #000;">421.2 / &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; / &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; / SMP / 2026</td>
                <td style="width: 35%; text-align: right; color: #000;">{hari_ini_str}</td>
            </tr>
            <tr>
                <td style="color: #000;">Sifat</td>
                <td style="color: #000;">:</td>
                <td style="color: #000;">Penting</td>
                <td></td>
            </tr>
            <tr>
                <td style="color: #000;">Lampiran</td>
                <td style="color: #000;">:</td>
                <td style="color: #000;">-</td>
                <td></td>
            </tr>
            <tr>
                <td style="color: #000;">Perihal</td>
                <td style="color: #000;">:</td>
                <td style="color: #000;"><b>Surat Pemanggilan Orang Tua / Wali Murid</b></td>
                <td></td>
            </tr>
        </table>
        
        <p style="font-size: 14px; margin-bottom: 20px; color: #000;">
            Kepada Yth.<br>
            Bapak/Ibu Orang Tua / Wali dari <b>{nama_siswa}</b> (Kelas: {kelas} / NISN: {nisn})<br>
            di Tempat
        </p>
        
        <p style="font-size: 14px; text-align: justify; line-height: 1.5; text-indent: 40px; color: #000;">
            Dengan hormat, Sehubungan dengan adanya hal penting yang perlu dikoordinasikan terkait perkembangan proses belajar mengajar anak didik kita, maka dengan ini kami mengharapkan kehadiran Bapak/Ibu Orang Tua / Wali Murid pada:
        </p>
        
        <table style="width: 90%; margin: 20px auto; font-size: 14px; line-height: 1.6; color: #000;">
            <tr>
                <td style="width: 25%; color: #000;">Hari / Tanggal</td>
                <td style="width: 3%; color: #000;">:</td>
                <td style="color: #000;">Sesuai Kesepakatan / Segera Setelah Menerima Surat Ini</td>
            </tr>
            <tr>
                <td style="color: #000;">Waktu</td>
                <td style="color: #000;">:</td>
                <td style="color: #000;">08.00 WIB s.d Selesai (Jam Kerja Sekolah)</td>
            </tr>
            <tr>
                <td style="color: #000;">Tempat</td>
                <td style="color: #000;">:</td>
                <td style="color: #000;">Ruang Kepala Sekolah / Ruang BK / Ruang Guru</td>
            </tr>
            <tr>
                <td style="color: #000;">Keperluan</td>
                <td style="color: #000;">:</td>
                <td style="color: #000;">
                    Koordinasi dan Klarifikasi terkait pelanggaran/catatan: <br>
                    <span style="color: red; font-weight: bold;">[ {alasan} ]</span> <br>
                    <i>Detail Catatan: {detail_kasus}</i>
                </td>
            </tr>
        </table>
        
        <p style="font-size: 14px; text-align: justify; line-height: 1.5; text-indent: 40px; margin-bottom: 30px; color: #000;">
            Meningat pentingnya permasalahan ini demi kebaikan masa depan putra/putri Bapak/Ibu, kami sangat mengharapkan kehadiran Bapak/Ibu tepat pada waktunya dan tidak diwakilkan. Demikian surat undangan ini kami sampaikan, atas perhatian dan kerja samanya kami ucapkan terima kasih.
        </p>
        
        <table style="width: 100%; font-size: 14px; margin-top: 40px; color: #000;">
            <tr>
                <td style="width: 60%;"></td>
                <td style="text-align: center; color: #000;">
                    Mengetahui,<br>
                    <b>Kepala Satuan Pendidikan</b>
                    <br><br><br><br><br>
                    <u><b>( {bio['kepsek']} )</b></u><br>
                    NIP. {bio['nip_kepsek']}
                </td>
            </tr>
        </table>
    </div>
    '''
    return html_content

def buat_rekap_dinas_html(kelas, bulan, tahun, df_rekap, nama_wali_kelas):
    hari_ini_str = datetime.date.today().strftime("%d %B %Y")
    bio = ambil_biodata_sekolah()
    
    baris_siswa_html = ""
    for idx, row in df_rekap.iterrows():
        status_keterangan = "Sangat Baik"
        warna_teks = "#000"
        if row['Total Alpa'] >= 3:
            status_keterangan = "Butuh Pemanggilan"
            warna_teks = "red"
        elif row['Total Alpa'] > 0:
            status_keterangan = "Peringatan Pembinaan"
            warna_teks = "orange"
            
        baris_siswa_html += f'''
        <tr>
            <td style="border: 1px solid #000; padding: 6px; text-align: center; color: #000;">{idx+1}</td>
            <td style="border: 1px solid #000; padding: 6px; text-align: center; color: #000;">{row['NISN']}</td>
            <td style="border: 1px solid #000; padding: 6px; color: #000;">{row['Nama Siswa']}</td>
            <td style="border: 1px solid #000; padding: 6px; text-align: center; color: #000;">{row['Total Hadir']}</td>
            <td style="border: 1px solid #000; padding: 6px; text-align: center; color: #000;">{row['Total Sakit/Izin']}</td>
            <td style="border: 1px solid #000; padding: 6px; text-align: center; color: #000;">{row['Total Alpa']}</td>
            <td style="border: 1px solid #000; padding: 6px; text-align: center; font-style: italic; color: {warna_teks}; font-weight: bold;">{status_keterangan}</td>
        </tr>
        '''

    html_document = f'''
    <div style="font-family: 'Times New Roman', Times, serif; padding: 20px; color: #000; background: #fff;">
        <div style="text-align: center; border-bottom: 5px double #000; padding-bottom: 10px; margin-bottom: 20px;">
            <h3 style="margin: 0; text-transform: uppercase; font-size: 18px; color: #000;">{bio['kab_kota']}</h3>
            <h2 style="margin: 5px 0; text-transform: uppercase; font-size: 22px; color: #000;">{bio['dinas']}</h2>
            <h1 style="margin: 5px 0; text-transform: uppercase; font-size: 24px; font-weight: bold; color: #000;">{bio['sekolah']}</h1>
            <p style="margin: 0; font-size: 12px; font-style: italic; color: #000;">{bio['alamat']}</p>
        </div>
        
        <div style="text-align: center; text-decoration: underline; text-transform: uppercase; font-weight: bold; font-size: 16px; margin-top: 10px; color: #000;">
            LAPORAN REKAPITULASI ABSENSI BULANAN SISWA
        </div>
        <div style="text-align: center; font-size: 14px; margin-bottom: 25px; color: #000;">
            Nomor: 421.2 / &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; / &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; / SMP / {tahun}
        </div>
        
        <table style="width: 100%; font-size: 14px; margin-bottom: 15px; color: #000; line-height: 1.6;">
            <tr>
                <td style="width: 20%; color: #000;">Fungsi Jabatan</td>
                <td style="width: 2%; color: #000;">:</td>
                <td style="width: 78%; color: #000;"><b>Guru Kelas / Wali Kelas</b></td>
            </tr>
            <tr>
                <td style="color: #000;">Kelas</td>
                <td style="color: #000;">:</td>
                <td style="color: #000;"><b>{kelas}</b></td>
            </tr>
            <tr>
                <td style="color: #000;">Periode Laporan</td>
                <td style="color: #000;">:</td>
                <td style="color: #000;">Bulan {bulan} Tahun {tahun}</td>
            </tr>
        </table>
        
        <p style="font-size: 14px; text-align: justify; text-indent: 40px; color: #000; margin-bottom: 15px;">
            Berdasarkan hasil rekapitulasi data kehadiran digital pada Sistem Absensi Terpadu, berikut dilampirkan berkas laporan rekapitulasi siswa yang memerlukan perhatian khusus serta pengawasan berkala selama periode berjalan:
        </p>
        
        <table style="width: 100%; border-collapse: collapse; font-size: 14px; margin-bottom: 25px;">
            <thead>
                <tr style="background-color: #f2f2f2;">
                    <th style="border: 1px solid #000; padding: 8px; text-align: center; color: #000;">No</th>
                    <th style="border: 1px solid #000; padding: 8px; text-align: center; color: #000;">NISN</th>
                    <th style="border: 1px solid #000; padding: 8px; text-align: left; color: #000;">Nama Siswa</th>
                    <th style="border: 1px solid #000; padding: 8px; text-align: center; color: #000;">Hadir</th>
                    <th style="border: 1px solid #000; padding: 8px; text-align: center; color: #000;">Sakit/Izin</th>
                    <th style="border: 1px solid #000; padding: 8px; text-align: center; color: #000;">Alpa</th>
                    <th style="border: 1px solid #000; padding: 8px; text-align: center; color: #000;">Keterangan Status</th>
                </tr>
            </thead>
            <tbody>
                {baris_siswa_html}
            </tbody>
        </table>
        
        <p style="font-size: 14px; text-align: justify; text-indent: 40px; color: #000; margin-bottom: 30px;">
            Demikian laporan rekapitulasi bulanan ini dibuat dengan sebenar-benarnya untuk digunakan sebagai landasan berkas pembinaan kedisiplinan siswa, koordinasi berkala bersama orang tua/wali murid, serta arsip administratif sekolah.
        </p>
        
        <table style="width: 100%; font-size: 14px; margin-top: 40px; color: #000;">
            <tr>
                <td style="width: 50%; text-align: center; vertical-align: top; color: #000;">
                    Mengetahui,<br>
                    <b>Kepala Satuan Pendidikan</b>
                    <br><br><br><br><br>
                    <u><b>( {bio['kepsek']} )</b></u><br>
                    NIP. {bio['nip_kepsek']}
                </td>
                <td style="width: 50%; text-align: center; vertical-align: top; color: #000;">
                    {hari_ini_str}<br>
                    <b>Guru Kelas / Wali Kelas</b>
                    <br><br><br><br><br>
                    <u><b>( {nama_wali_kelas} )</b></u><br>
                    NIP. ........................................
                </td>
            </tr>
        </table>
    </div>
    '''
    return html_document

# ==========================================
# HALAMAN LOGIN SYSTEM
# ==========================================
if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center; color: #4F46E5;'>💎 LOGIN ABSENSI DIGITAL PREMIUM</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Username / NIP")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Masuk Ke Sistem Premium", use_container_width=True)
            
            if submitted:
                hashed_input = hash_password(password)
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("SELECT role, nama, kelas_tugas FROM users WHERE username=? AND (password=? OR password=?)", (username, password, hashed_input))
                user = c.fetchone()
                conn.close()
                
                if user:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.role = user[0]
                    st.session_state.nama = user[1]
                    st.session_state.kelas_tugas = user[2] if user[2] else "Belum Diatur"
                    st.rerun()
                else:
                    st.error("Username atau Password keliru. Silakan hubungi operator.")
    st.stop()

# ==========================================
# SIDEBAR LOGOUT & INFO
# ==========================================
st.sidebar.markdown(f"**Pengguna:** {st.session_state.nama} ({st.session_state.role})")
if st.session_state.role == "Guru":
    st.sidebar.info(f"📍 **Hak Akses:** Kelas {st.session_state.kelas_tugas}")

# ==========================================
# INTERFACE: DASHBOARD ADMIN (KEPALA SEKOLAH)
# ==========================================
if st.session_state.role == "Admin":
    st.sidebar.markdown("### 🏛️ MENU UTAMA KEPSEK")
    menu_admin = st.sidebar.radio("Pilih Menu Panel:", [
        "📊 Grafik Analisis Makro",
        "📥 Pengaturan Biodata & Kop Sekolah",
        "📥 Kotak Aduan & Curhat Guru",
        "🚨 Rekap Siswa Bermasalah",
        "✉️ Surat Pemanggilan Ortu",
        "🔄 Kenaikan Kelas Massal",
        "📝 Laporan Tindak Lanjut Guru",
        "📑 Cetak Laporan Bulanan",
        "👥 Manajemen Akun Guru"
    ])
    
    if st.sidebar.button("Keluar dari Aplikasi", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()

    st.title("🏛️ Panel Utama Kepala Sekolah (Premium Admin)")
    
    tgl_pantau = st.date_input("Pilih Tanggal Pantauan Laporan", datetime.date.today())
    conn = get_db_connection()
    total_siswa = conn.execute("SELECT COUNT(*) FROM siswa").fetchone()[0]
    total_hadir = conn.execute("SELECT COUNT(*) FROM absensi WHERE tanggal=? AND status='hadir' AND jam_ke='Harian'", (str(tgl_pantau),)).fetchone()[0]
    total_sakit = conn.execute("SELECT COUNT(*) FROM absensi WHERE tanggal=? AND status='sakit' AND jam_ke='Harian'", (str(tgl_pantau),)).fetchone()[0]
    total_alpa = conn.execute("SELECT COUNT(*) FROM absensi WHERE tanggal=? AND status='tidak_hadir' AND jam_ke='Harian'", (str(tgl_pantau),)).fetchone()[0]
    conn.close()
    persen_hadir = (total_hadir / total_siswa * 100) if total_siswa > 0 else 0
    
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1: st.metric(label="Total Siswa Terdaftar", value=f"{total_siswa} Anak")
    with col_m2: st.metric(label="Persentase Kehadiran Pagi (Harian)", value=f"{persen_hadir:.1f}%")
    with col_m3: st.metric(label="Siswa Sakit / Izin Harian", value=f"{total_sakit} Anak")
    with col_m4: st.metric(label="Siswa Alpa Harian", value=f"{total_alpa} Anak")
    st.write("---")

    if menu_admin == "📥 Pengaturan Biodata & Kop Sekolah":
        st.subheader("📥 Manajemen Instansi & Identitas Kepala Sekolah")
        st.write("Data yang diisi di sini akan otomatis menjadi Kop Surat dan identitas tanda tangan resmi pada seluruh berkas aplikasi.")
        
        current_bio = ambil_biodata_sekolah()
        
        with st.form("form_biodata_sekolah_db"):
            in_kab = st.text_input("Nama Tingkat Wilayah (Baris 1 Kop)", value=current_bio['kab_kota'])
            in_dinas = st.text_input("Nama Instansi / Dinas (Baris 2 Kop)", value=current_bio['dinas'])
            in_sekolah = st.text_input("Nama Satuan Pendidikan / Sekolah (Baris 3 Kop)", value=current_bio['sekolah'])
            in_alamat = st.text_input("Alamat Lengkap & Kontak Sekolah (Baris 4 Kop)", value=current_bio['alamat'])
            
            st.markdown("##### 🖋️ Identitas Kepala Sekolah")
            in_kepsek = st.text_input("Nama Lengkap Kepala Sekolah", value=current_bio['kepsek'])
            in_nip = st.text_input("NIP Kepala Sekolah", value=current_bio['nip_kepsek'])
            
            if st.form_submit_button("💾 Simpan Perubahan Biodata Instansi", use_container_width=True):
                conn = get_db_connection()
                c = conn.cursor()
                c.execute('''UPDATE biodata_sekolah SET 
                                nama_kab_kota=?, nama_dinas=?, nama_sekolah=?, alamat_sekolah=?, nama_kepsek=?, nip_kepsek=? 
                             WHERE id=1''', (in_kab, in_dinas, in_sekolah, in_alamat, in_kepsek, in_nip))
                conn.commit()
                conn.close()
                st.success("Sukses! Biodata instansi berhasil diperbarui secara permanen.")
                st.rerun()

    elif menu_admin == "📊 Grafik Analisis Makro":
        st.subheader("Analisis Grafik Kehadiran Siswa (Umum/Harian)")
        conn = get_db_connection()
        df_absensi = pd.read_sql_query('''
            SELECT s.kelas, a.status, COUNT(a.id) as jumlah 
            FROM siswa s 
            LEFT JOIN absensi a ON s.nisn = a.nisn AND a.tanggal = ? AND a.jam_ke = 'Harian'
            GROUP BY s.kelas, a.status
        ''', conn, params=(str(tgl_pantau),))
        conn.close()
        df_absensi['status'] = df_absensi['status'].fillna('Belum Absen')
        if not df_absensi.empty:
            fig = px.bar(df_absensi, x='kelas', y='jumlah', color='status', 
                         title=f"Grafik Kehadiran Per Kelas Tanggal {tgl_pantau}",
                         barmode='group', color_discrete_map={'hadir':'#22C55E','sakit':'#FBBF24','tidak_hadir':'#EF4444','Belum Absen':'#9CA3AF'})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Belum ada transaksi absensi masuk pada tanggal terpilih.")

    elif menu_admin == "📥 Kotak Aduan & Curhat Guru":
        st.subheader("📥 Kotak Masuk Aduan, Saran, & Curcuran Hati Guru")
        st.info("Halaman ini hanya bisa diakses oleh Kepala Sekolah. Semua masukan bersifat rahasia untuk menjaga keterbukaan komunikasi sekolah.")
        
        conn = get_db_connection()
        df_aduan_admin = pd.read_sql_query("SELECT id, tanggal, guru_pengirim as [Dari Guru], jenis_aduan as [Kategori], isi_curhat as [Isi Pesan/Aduan], status_tindak_lanjut as [Status], catatan_kepsek as [Catatan Kepsek] FROM aduan_curhat ORDER BY id DESC", conn)
        conn.close()
        
        if df_aduan_admin.empty:
            st.info("Belum ada aduan atau saran yang masuk dari guru-guru.")
        else:
            for idx, r_aduan in df_aduan_admin.iterrows():
                with st.expander(f"✉️ [{r_aduan['Kategori']}] Dari: {r_aduan['Dari Guru']} | Tanggal: {r_aduan['tanggal']} ({r_aduan['Status']})"):
                    st.markdown(f"**Isi Curhat/Komplain:**\n> {r_aduan['Isi Pesan/Aduan']}")
                    st.write(f"**Tanggapan/Catatan Saat Ini:** {r_aduan['Catatan Kepsek']}")
                    
                    with st.form(f"tanggapi_aduan_{r_aduan['id']}"):
                        isi_tanggapan = st.text_area("Tulis Tanggapan / Tindak Lanjut Kepala Sekolah:", value=r_aduan['Catatan Kepsek'] if r_aduan['Catatan Kepsek'] != '-' else "")
                        status_baru = st.selectbox("Ubah Status Laporan:", ["Belum Dibaca", "Sedang Ditinjau", "Sudah Ditindaklanjuti"], index=["Belum Dibaca", "Sedang Ditinjau", "Sudah Ditindaklanjuti"].index(r_aduan['Status']))
                        
                        if st.form_submit_button("💾 Simpan Tanggapan Kepsek"):
                            conn = get_db_connection()
                            c = conn.cursor()
                            c.execute("UPDATE aduan_curhat SET status_tindak_lanjut=?, catatan_kepsek=? WHERE id=?", (status_baru, isi_tanggapan if isi_tanggapan else '-', r_aduan['id']))
                            conn.commit()
                            conn.close()
                            st.success("Tanggapan berhasil disimpan!")
                            st.rerun()

    elif menu_admin == "🚨 Rekap Siswa Bermasalah":
        st.subheader("🚨 Daftar Kronis Siswa Bermasalah (Sering Alpa)")
        st.write("Sistem menyaring otomatis siswa yang memiliki akumulasi Alpa terbanyak di sekolah untuk tindakan preventif.")
        
        conn = get_db_connection()
        df_kronis_admin = pd.read_sql_query('''
            SELECT s.kelas as [Kelas], s.nisn as [NISN], s.nama as [Nama Siswa], s.no_wa_orang_tua as [WA Orang Tua],
                   COUNT(a.id) as [Total Alpa Terakumulasi]
            FROM siswa s
            JOIN absensi a ON s.nisn = a.nisn
            WHERE LOWER(a.status) = 'tidak_hadir'
            GROUP BY s.nisn
            HAVING [Total Alpa Terakumulasi] >= 1
            ORDER BY [Total Alpa Terakumulasi] DESC
        ''', conn)
        conn.close()
        
        if df_kronis_admin.empty:
            st.success("Luar biasa! Belum ada siswa yang tercatat Alpa di sekolah ini.")
        else:
            st.dataframe(df_kronis_admin, use_container_width=True)

    elif menu_admin == "✉️ Surat Pemanggilan Ortu":
        st.subheader("✉️ Generator Surat Pemanggilan Orang Tua / Wali Siswa Otomatis")
        st.write("Gunakan fitur ini untuk membuat surat resmi fisik/cetak bagi siswa yang bermasalah (Sering Alfa, Bolos, Tawuran, Perundungan, dll).")
        
        conn = get_db_connection()
        list_siswa_db = conn.execute("SELECT nisn, nama, kelas FROM siswa ORDER BY kelas, nama").fetchall()
        conn.close()
        
        if not list_siswa_db:
            st.warning("Belum ada data siswa dalam database sekolah.")
        else:
            opsi_siswa = [f"{r[1]} ({r[2]}) - NISN: {r[0]}" for r in list_siswa_db]
            
            with st.form("form_surat_resmi"):
                siswa_terpilih_str = st.selectbox("Cari dan Pilih Siswa Bermasalah:", opsi_siswa)
                index_terpilih = opsi_siswa.index(siswa_terpilih_str)
                siswa_data = list_siswa_db[index_terpilih]
                
                jenis_cases = st.selectbox("Jenis Pelanggaran / Alasan Pemanggilan:", [
                    "Akumulasi Absensi Alpa Terlalu Banyak (3-5 Kali / Lebih)",
                    "Siswa Sering Bolos Saat Jam Pelajaran Berlangsung",
                    "Membuat Keonaran / Keributan di Lingkungan Sekolah",
                    "Terlibat Tindakan Perundungan (Bullying) / Kekerasan Fisik",
                    "Pelanggaran Aturan Ketertiban Berat Lainnya"
                ])
                
                detail_tambahan = st.text_area("Detail/Catatan Tambahan Kasus (Misal: Alpa 4 hari berturut-turut, membully teman sekelas 7B):", placeholder="Tulis rincian kronologi singkat di sini...")
                
                tombol_generate = st.form_submit_button("🔥 Buat Draf Surat Resmi")
                
                if tombol_generate:
                    html_surat = buat_surat_html(siswa_data[1], siswa_data[2], siswa_data[0], jenis_cases, detail_tambahan if detail_tambahan else "-")
                    st.session_state['html_surat_temp'] = html_surat
                    st.session_state['nama_siswa_temp'] = siswa_data[1]
                    st.success("Surat Berhasil Dibuat! Silakan lihat pratinjau di bawah ini.")
            
            if 'html_surat_temp' in st.session_state:
                st.markdown("### 📄 Pratinjau Surat Resmi (Siap Cetak)")
                st.components.v1.html(
                    f"""
                    <div style="background-color: #ffffff; padding: 15px; border-radius: 8px; border: 1px solid #ccc; min-height: 600px;">
                        {st.session_state['html_surat_temp']}
                    </div>
                    """,
                    height=700,
                    scrolling=True
                )
                
                st.write("")
                st.download_button(
                    label="🖨️ Unduh Surat Resmi Untuk Dicetak (.html)",
                    data=st.session_state['html_surat_temp'],
                    file_name=f"Surat_Pemanggilan_{st.session_state['nama_siswa_temp']}.html",
                    mime="text/html",
                    use_container_width=True
                )

    elif menu_admin == "🔄 Kenaikan Kelas Massal":
        st.subheader("🔄 Fitur Kenaikan & Perpindahan Kelas Massal (Tahun Ajaran Baru)")
        conn = get_db_connection()
        list_kelas_asal = [r[0] for r in conn.execute("SELECT DISTINCT kelas FROM siswa WHERE kelas != ''").fetchall()]
        conn.close()
        col_up1, col_up2 = st.columns(2)
        with col_up1:
            kelas_asal = st.selectbox("Pilih Kelas Asal (Saat Ini):", list_kelas_asal, key="asal_massal")
        with col_up2:
            kelas_tujuan = st.text_input("Ketik Kelas Tujuan Baru (Misal: 7B, 8A, LULUS):").strip().upper()
        check_konfirmasi_naik = st.checkbox(f"Saya setuju memindahkan massal semua siswa kelas {kelas_asal} menuju kelas {kelas_tujuan}")
        if st.button("🚀 Proses Pindah Kelas Massal", type="primary"):
            if kelas_tujuan == "": st.error("Kelas tujuan baru wajib diisi!")
            elif not check_konfirmasi_naik: st.error("Wajib centang kotak konfirmasi persetujuan!")
            else:
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("UPDATE siswa SET kelas = ? WHERE kelas = ?", (kelas_tujuan, kelas_asal))
                jumlah_terubah = c.rowcount
                conn.commit()
                conn.close()
                st.success(f"Sukses! Sebanyak {jumlah_terubah} siswa dari kelas {kelas_asal} dipindahkan ke kelas {kelas_tujuan}.")
                st.rerun()

    elif menu_admin == "📝 Laporan Tindak Lanjut Guru":
        st.subheader("Pantauan Laporan Khusus Siswa Bermasalah (Alpa)")
        conn = get_db_connection()
        df_laporan = pd.read_sql_query('''
            SELECT l.tanggal, s.kelas, s.nama, l.catatan, l.status_wa 
            FROM laporan_tindak_lanjut l
            JOIN siswa s ON l.nisn = s.nisn
            ORDER BY l.id DESC
        ''', conn)
        conn.close()
        st.dataframe(df_laporan, use_container_width=True)

    elif menu_admin == "📑 Cetak Laporan Bulanan":
        st.subheader("Ekspor Laporan Rekapitulasi Bulanan (Umum)")
        col_bln, col_thn = st.columns(2)
        with col_bln: bulan_pilih = st.selectbox("Pilih Bulan", [f"{i:02d}" for i in range(1, 13)], index=datetime.date.today().month - 1, key="bln_admin")
        with col_thn: tahun_pilih = st.selectbox("Pilih Tahun", [str(datetime.date.today().year), str(datetime.date.today().year - 1)], key="thn_admin")
        filter_periode = f"{tahun_pilih}-{bulan_pilih}-%"
        if st.button("Generate Rekap Bulanan Excel", type="primary"):
            conn = get_db_connection()
            df_rekap = pd.read_sql_query('''
                SELECT s.kelas, s.nisn, s.nama,
                       SUM(CASE WHEN LOWER(a.status) = 'hadir' AND a.jam_ke = 'Harian' THEN 1 ELSE 0 END) as Total_Hadir,
                       SUM(CASE WHEN LOWER(a.status) = 'sakit' AND a.jam_ke = 'Harian' THEN 1 ELSE 0 END) as Total_Sakit,
                       SUM(CASE WHEN LOWER(a.status) = 'tidak_hadir' AND a.jam_ke = 'Harian' THEN 1 ELSE 0 END) as Total_Alpa
                FROM siswa s
                LEFT JOIN absensi a ON s.nisn = a.nisn AND a.tanggal LIKE ?
                GROUP BY s.nisn
                ORDER BY s.kelas, s.nama
            ''', conn, params=(filter_periode,))
            conn.close()
            if not df_rekap.empty:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer: df_rekap.to_excel(writer, sheet_name='Rekap Bulanan', index=False)
                st.success("File Excel Berhasil Dibuat!")
                st.download_button(label="📥 Unduh File Rekap Absensi (.xlsx)", data=buffer.getvalue(), file_name=f"Rekap_Absensi_{bulan_pilih}_{tahun_pilih}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else: st.warning("Tidak ditemukan data absensi pada periode bulan ini.")

    elif menu_admin == "👥 Manajemen Akun Guru":
        st.subheader("Registrasi & Manajemen Akun Guru")
        col_input, col_list = st.columns([1, 2])
        with col_input:
            st.markdown("#### ➕ Tambah Guru Baru")
            with st.form("tambah_guru", clear_on_submit=True):
                u_guru = st.text_input("Username Guru (NIP)")
                p_guru = st.text_input("Password Baru", type="password")
                n_guru = st.text_input("Nama Lengkap Guru")
                k_guru = st.text_input("Tugas di Kelas (Isi 'SEMUA' untuk Guru Piket / Guru Mapel)")
                submit_guru = st.form_submit_button("Daftarkan Akun")
                if submit_guru and u_guru and p_guru and k_guru:
                    if len(p_guru) < 6: st.error("Password wajib minimal 6 karakter.")
                    else:
                        hashed_p_guru = hash_password(p_guru)
                        try:
                            conn = get_db_connection()
                            c = conn.cursor()
                            c.execute("INSERT INTO users VALUES (?, ?, 'Guru', ?, ?)", (u_guru, hashed_p_guru, n_guru, k_guru.strip().upper()))
                            conn.commit()
                            st.success(f"Akun {n_guru} berhasil didaftarkan!")
                            st.rerun()
                        except sqlite3.IntegrityError: st.error("Username/NIP sudah terdaftar.")
                        finally: conn.close()
        with col_list:
            st.markdown("#### 📋 Daftar Akun Guru Aktif")
            conn = get_db_connection()
            df_guru = pd.read_sql_query("SELECT username as [Username/NIP], nama as [Nama Guru], kelas_tugas as [Kelas Tugas] FROM users WHERE role='Guru'", conn)
            conn.close()
            if not df_guru.empty:
                for idx, row in df_guru.iterrows():
                    kelas_tampil = row['Kelas Tugas'] if row['Kelas Tugas'] else "Belum Set"
                    with st.expander(f"👤 {row['Nama Guru']} [Akses: {kelas_tampil}]"):
                        with st.form(f"form_edit_{row['Username/NIP']}"):
                            edit_nama = st.text_input("Nama Lengkap Baru", value=row['Nama Guru'])
                            edit_kelas = st.text_input("Kelas Tugas Baru", value=kelas_tampil)
                            edit_pass = st.text_input("Password Baru (Kosongkan jika tetap)", type="password")
                            check_hapus = st.checkbox("Saya ingin menghapus akun ini", key=f"del_chk_{row['Username/NIP']}")
                            
                            col_btn1, col_btn2 = st.columns(2)
                            with col_btn1: btn_simpan = st.form_submit_button("💾 Simpan Perubahan", use_container_width=True)
                            with col_btn2: btn_hapus = st.form_submit_button("🗑️ Hapus Akun Ini", use_container_width=True)
                                
                            if btn_simpan:
                                conn = get_db_connection()
                                c = conn.cursor()
                                if edit_pass.strip() != "":
                                    c.execute("UPDATE users SET nama=?, kelas_tugas=?, password=? WHERE username=?", (edit_nama, edit_kelas.strip().upper(), hash_password(edit_pass), row['Username/NIP']))
                                else:
                                    c.execute("UPDATE users SET nama=?, kelas_tugas=? WHERE username=?", (edit_nama, edit_kelas.strip().upper(), row['Username/NIP']))
                                conn.commit()
                                conn.close()
                                st.success("Data diperbarui!")
                                st.rerun()
                            if btn_hapus and check_hapus:
                                conn = get_db_connection()
                                c = conn.cursor()
                                c.execute("DELETE FROM users WHERE username=?", (row['Username/NIP'],))
                                conn.commit()
                                conn.close()
                                st.rerun()

# ==========================================
# INTERFACE: MENU GURU
# ==========================================
elif st.session_state.role == "Guru":
    st.title("👨‍🏫 Panel Manajemen Guru")
    
    menu_guru = st.sidebar.radio("Pilih Menu", [
        "📝 Input Absensi Harian", 
        "🚨 Rekap Siswa Bermasalah Kelas Saya", 
        "📬 Pojok Curhat & Saran ke Kepsek",
        "📑 Rekap Bulanan Kelas Saya", 
        "📥 Sinkronisasi Data Dapodik"
    ])
    
    if st.sidebar.button("Keluar dari Aplikasi", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()
        
    hak_akses = st.session_state.kelas_tugas.strip().upper()
    conn = get_db_connection()
    list_kelas_db = [r[0] for r in conn.execute("SELECT DISTINCT kelas FROM siswa WHERE kelas != '' AND kelas != '-'").fetchall()]
    conn.close()
    if not list_kelas_db: list_kelas_db = ["6A"]
        
    if hak_akses == "SEMUA": pilihan_kelas = st.sidebar.selectbox("Pilih Kelas Sasaran", list_kelas_db)
    else: pilihan_kelas = hak_akses

    hari_ini = str(datetime.date.today())

    if menu_guru == "🚨 Rekap Siswa Bermasalah Kelas Saya":
        st.subheader(f"🚨 Daftar Siswa Bermasalah (Sering Alpa) — Kelas {pilihan_kelas}")
        st.write("Siswa di bawah ini diurutkan berdasarkan akumulasi ketidakhadiran (Alpa) paling tinggi di kelas Anda.")
        
        conn = get_db_connection()
        df_kronis_guru = pd.read_sql_query('''
            SELECT s.nisn as [NISN], s.nama as [Nama Siswa], s.no_wa_orang_tua as [WA Orang Tua],
                   COUNT(a.id) as [Total Alpa]
            FROM siswa s
            JOIN absensi a ON s.nisn = a.nisn
            WHERE s.kelas = ? AND LOWER(a.status) = 'tidak_hadir'
            GROUP BY s.nisn
            ORDER BY [Total Alpa] DESC
        ''', conn, params=(pilihan_kelas,))
        conn.close()
        
        if df_kronis_guru.empty:
            st.success(f"Alhamdulillah! Tidak ada siswa kelas {pilihan_kelas} yang memiliki riwayat Alpa.")
        else:
            st.dataframe(df_kronis_guru, use_container_width=True)

    elif menu_guru == "📬 Pojok Curhat & Saran ke Kepsek":
        st.subheader("📬 Pojok Curhat & Kotak Saran Guru (Rahasia & Langsung ke Kepsek)")
        st.write("Punya kendala belajar, saran sekolah, atau komplain kehadiran guru lain yang enggan dibahas saat rapat? Sampaikan di sini secara tertutup.")
        
        with st.form("form_curhat_guru", clear_on_submit=True):
            kategori_aduan = st.selectbox("Pilih Kategori Penyampaian:", ["Masalah Siswa/Wali Murid", "Saran Sarana & Prasarana", "Komplain Kedisiplinan Guru/Staf", "Curhat Masalah Pribadi"])
            isi_aduan = st.text_area("Tuliskan pesan, kronologi, atau saran Anda secara lengkap:")
            
            if st.form_submit_button("🚀 Kirim Rahasia ke Kepala Sekolah"):
                if isi_aduan.strip() == "": st.error("Isi pesan tidak boleh kosong!")
                else:
                    conn = get_db_connection()
                    c = conn.cursor()
                    c.execute("INSERT INTO aduan_curhat (tanggal, guru_pengirim, jenis_aduan, isi_curhat) VALUES (?, ?, ?, ?)", (hari_ini, st.session_state.nama, kategori_aduan, isi_aduan))
                    conn.commit()
                    conn.close()
                    st.success("Sukses! Pesan Anda telah terkirim langsung ke meja digital Kepala Sekolah.")
        
        st.write("---")
        st.markdown("#### 📜 Riwayat Tanggapan Kepala Sekolah")
        conn = get_db_connection()
        df_riwayat_curhat = pd.read_sql_query("SELECT tanggal as [Tanggal], jenis_aduan as [Kategori], isi_curhat as [Aduan Saya], status_tindak_lanjut as [Status Kepsek], catatan_kepsek as [Tanggapan Kepsek] FROM aduan_curhat WHERE guru_pengirim = ? ORDER BY id DESC", conn, params=(st.session_state.nama,))
        conn.close()
        if df_riwayat_curhat.empty: st.caption("Belum ada riwayat curhat sebelumnya.")
        else: st.dataframe(df_riwayat_curhat, use_container_width=True)

    elif menu_guru == "📑 Rekap Bulanan Kelas Saya":
        st.subheader(f"📑 Menu Rekapitulasi Kehadiran Bulanan — Kelas {pilihan_kelas}")
        col_g1, col_g2 = st.columns(2)
        with col_g1: g_bulan = st.selectbox("Pilih Bulan", [f"{i:02d}" for i in range(1, 13)], index=datetime.date.today().month - 1, key="g_bln")
        with col_g2: g_tahun = st.selectbox("Pilih Tahun", [str(datetime.date.today().year), str(datetime.date.today().year - 1)], key="g_thn")
        g_periode = f"{g_tahun}-{g_bulan}-%"
        
        conn = get_db_connection()
        df_rekap_guru = pd.read_sql_query('''
            SELECT s.kelas as [Kelas], s.nisn as [NISN], s.nama as [Nama Siswa],
                   SUM(CASE WHEN LOWER(a.status) = 'hadir' AND a.jam_ke = 'Harian' THEN 1 ELSE 0 END) as [Total Hadir],
                   SUM(CASE WHEN LOWER(a.status) = 'sakit' AND a.jam_ke = 'Harian' THEN 1 ELSE 0 END) as [Total Sakit/Izin],
                   SUM(CASE WHEN LOWER(a.status) = 'tidak_hadir' AND a.jam_ke = 'Harian' THEN 1 ELSE 0 END) as [Total Alpa]
            FROM siswa s
            LEFT JOIN absensi a ON s.nisn = a.nisn AND a.tanggal LIKE ?
            WHERE s.kelas = ?
            GROUP BY s.nisn
            ORDER BY s.nama ASC
        ''', conn, params=(g_periode, pilihan_kelas))
        conn.close()
        
        col_btn_excel, col_btn_surat = st.columns(2)
        
        with col_btn_excel:
            if st.button("📊 Unduh Rekapan Excel (.xlsx)", type="primary", use_container_width=True):
                if not df_rekap_guru.empty:
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer: df_rekap_guru.to_excel(writer, sheet_name='Rekap', index=False)
                    st.download_button(label=f"📥 Ambil File Excel Kelas {pilihan_kelas}", data=buffer.getvalue(), file_name=f"Rekap_{pilihan_kelas}_{g_bulan}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                else: st.warning("Tidak ditemukan data absensi periode bulan ini.")
                
        with col_btn_surat:
            if st.button("🖨️ Buat Surat Laporan Dinas (.html)", use_container_width=True):
                if not df_rekap_guru.empty:
                    html_dinas = buat_rekap_dinas_html(pilihan_kelas, g_bulan, g_tahun, df_rekap_guru, st.session_state.nama)
                    st.session_state['html_rekap_dinas_temp'] = html_dinas
                    st.success("Surat Laporan Dinas Berhasil Dibuat!")
                else:
                    st.warning("Tidak dapat membuat laporan dinas karena data bulan ini masih kosong.")
                    
        if 'html_rekap_dinas_temp' in st.session_state:
            st.write("---")
            st.markdown("### 📄 Pratinjau Surat Laporan Dinas Bulanan (Siap Cetak Fisik)")
            st.components.v1.html(
                f"""
                <div style="background-color: #ffffff; padding: 15px; border-radius: 8px; border: 1px solid #ccc; min-height: 500px;">
                    {st.session_state['html_rekap_dinas_temp']}
                </div>
                """,
                height=600,
                scrolling=True
            )
            st.download_button(
                label="📥 Download Surat Laporan Dinas Resmi Resmi (.html)",
                data=st.session_state['html_rekap_dinas_temp'],
                file_name=f"Laporan_Dinas_Bulanan_Kelas_{pilihan_kelas}_{g_bulan}.html",
                mime="text/html",
                use_container_width=True
            )

    elif menu_guru == "📥 Sinkronisasi Data Dapodik":
        st.subheader(f"Unggah Template Siswa Khusus Kelas {pilihan_kelas}")
        columns_template = ['Kelas', 'Nama', 'NISN', 'NIS', 'Tempat Lahir', 'Tanggal Lahir', 'Agama', 'NIK', 'Alamat', 'Nama Ayah', 'Pekerjaan Ayah', 'Nama Ibu', 'Pekerjaan Ibu', 'No WA Orang Tua']
        df_tpl = pd.DataFrame(columns=columns_template)
        tpl_buffer = io.BytesIO()
        with pd.ExcelWriter(tpl_buffer, engine='openpyxl') as writer: df_tpl.to_excel(writer, index=False)
        st.download_button(label="📄 Download Format Template Excel Dapodik", data=tpl_buffer.getvalue(), file_name=f"template_dapodik_kelas_{pilihan_kelas}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        uploaded_file = st.file_uploader("Upload File Excel Template Dapodik (.xlsx)", type=["xlsx"])
        if uploaded_file is not None:
            try:
                df_excel = pd.read_excel(uploaded_file)
                conn = get_db_connection()
                c = conn.cursor()
                sukses_import = 0
                for _, row in df_excel.iterrows():
                    if pd.isna(row['NISN']) or pd.isna(row['Nama']): continue
                    row = row.fillna('-')
                    c.execute('''INSERT OR REPLACE INTO siswa VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                              (str(row['NISN']).strip(), str(row['Nama']).strip(), str(row['Kelas']).strip().upper(), str(row['NIS']).strip(), str(row['Tempat Lahir']), str(row['Tanggal Lahir']), str(row['Agama']), str(row['NIK']), str(row['Alamat']), str(row['Nama Ayah']), str(row['Pekerjaan Ayah']), str(row['Nama Ibu']), str(row['Pekerjaan Ibu']), str(row['No WA Orang Tua']).strip()))
                    sukses_import += 1
                conn.commit()
                conn.close()
                st.success(f"Berhasil mengimpor {sukses_import} data siswa.")
            except Exception as e: st.error(f"Gagal membaca file: {e}")

        st.write("---")
        st.subheader(f"Tambah Siswa Secara Manual ke Kelas {pilihan_kelas}")
        with st.form("manual_siswa"):
            col1, col2 = st.columns(2)
            with col1:
                m_nama = st.text_input("Nama Lengkap Siswa")
                m_nisn = st.text_input("NISN")
                m_nis = st.text_input("NIS")
                m_wa = st.text_input("No WA Orang Tua")
            with col2:
                m_tl = st.text_input("Tempat Lahir")
                m_tgl = st.text_input("Tanggal Lahir")
                m_alamat = st.text_area("Alamat Rumah")
            submit_manual = st.form_submit_button("Simpan Data Siswa")
            if submit_manual and m_nisn and m_nama:
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("INSERT OR REPLACE INTO siswa (nisn, nama, kelas, nis, tempat_lahir, tanggal_lahir, no_wa_orang_tua, alamat) VALUES (?,?,?,?,?,?,?,?)", (m_nisn, m_nama, pilihan_kelas, m_nis, m_tl, m_tgl, m_wa, m_alamat))
                conn.commit()
                conn.close()
                st.success(f"Siswa {m_nama} berhasil dimasukkan ke kelas {pilihan_kelas}!")

    elif menu_guru == "📝 Input Absensi Harian":
        st.subheader(f"Isi Kehadiran Kelas Real-time")
        mode_absen = st.radio("Pilih Mode Pengisian Absen:", ["Wali Kelas / Umum (Harian)", "Mata Pelajaran (Per Jam Pelajaran)"], horizontal=True)
        if mode_absen == "Mata Pelajaran (Per Jam Pelajaran)":
            col_mp1, col_mp2 = st.columns(2)
            with col_mp1: val_mapel = st.selectbox("Mata Pelajaran", ["Bahasa Indonesia", "Matematika", "IPA", "IPS", "Bahasa Inggris", "Pendidikan Agama", "PJOK", "Seni Budaya"])
            with col_mp2: val_jam = st.selectbox("Jam Pelajaran Ke-", ["1-2 (07.00-08.20)", "3-4 (08.40-10.00)", "5-6 (10.20-11.40)", "7-8 (12.10-13.30)"])
            konteks_wa = f"Jam Pelajaran {val_jam} untuk Mata Pelajaran {val_mapel}"
        else:
            val_mapel = "Wali Kelas / Umum"
            val_jam = "Harian"
            konteks_wa = "Hari ini (Absensi Umum)"
            
        st.info(f"📋 **Kelas:** {pilihan_kelas} | 📚 **Mode:** {val_mapel} ({val_jam}) | 📅 **Tanggal:** {hari_ini}")
        
        with st.expander("➕ Tambah Siswa Baru Di Tengah Semester"):
            with st.form(f"form_cepat_tambah_{pilihan_kelas}", clear_on_submit=True):
                c_nama = st.text_input("Nama Lengkap Siswa Baru")
                c_nisn = st.text_input("NISN Siswa Baru")
                c_wa = st.text_input("No WA Orang Tua")
                submit_cepat = st.form_submit_button("Simpan Siswa Baru")
                if submit_cepat and c_nama and c_nisn:
                    conn = get_db_connection()
                    c = conn.cursor()
                    try:
                        c.execute("INSERT INTO siswa (nisn, nama, kelas, no_wa_orang_tua) VALUES (?, ?, ?, ?)", (c_nisn, c_nama, pilihan_kelas, c_wa))
                        conn.commit()
                        st.success(f"Berhasil menambahkan {c_nama} ke kelas {pilihan_kelas}!")
                        st.rerun()
                    except sqlite3.IntegrityError: st.error("Gagal! NISN sudah terdaftar.")
                    finally: conn.close()
        
        conn = get_db_connection()
        df_siswa_kelas = pd.read_sql_query('''
            SELECT s.nisn, s.nama, s.no_wa_orang_tua, s.nis, s.kelas, a.status 
            FROM siswa s 
            LEFT JOIN absensi a ON s.nisn = a.nisn AND a.tanggal = ? AND a.mapel = ? AND a.jam_ke = ?
            WHERE s.kelas = ?
            ORDER BY s.nama ASC
        ''', conn, params=(hari_ini, val_mapel, val_jam, pilihan_kelas))
        conn.close()
        
        if df_siswa_kelas.empty:
            st.warning(f"Belum ada data siswa di Kelas {pilihan_kelas}. Silakan upload melalui menu Dapodik terlebih dahulu.")
            st.stop()
            
        col_bulk, _ = st.columns([2, 2])
        with col_bulk:
            if st.button("⚡ Tandai Semua Siswa Belum Absen sebagai 'HADIR'", use_container_width=True):
                waktu_sekarang = datetime.datetime.now().strftime("%H:%M:%S")
                conn = get_db_connection()
                c = conn.cursor()
                bulk_count = 0
                for _, row in df_siswa_kelas.iterrows():
                    status_db = str(row['status']).strip().lower() if row['status'] else 'belum'
                    if status_db not in ['hadir', 'sakit', 'tidak_hadir']:
                        c.execute('''INSERT OR REPLACE INTO absensi (nisn, tanggal, mapel, jam_ke, status, waktu, guru_input) VALUES (?, ?, ?, ?, 'hadir', ?, ?)''', (row['nisn'], hari_ini, val_mapel, val_jam, waktu_sekarang, st.session_state.username))
                        bulk_count += 1
                conn.commit()
                conn.close()
                st.success(f"Berhasil menandai {bulk_count} siswa sebagai Hadir!")
                st.rerun()
                
        st.markdown("---")
        for idx, row in df_siswa_kelas.iterrows():
            status_clean = str(row['status']).strip().lower() if row['status'] else 'belum'
            if status_clean not in ['hadir', 'sakit', 'tidak_hadir', 'belum']: status_clean = 'belum'
            bg_color = "#FEE2E2" if status_clean == "tidak_hadir" else "#FFFFFF"
            
            with st.container():
                st.markdown(f"""<div style='background-color: {bg_color}; padding: 12px; border-radius: 8px; margin-bottom: 8px; border: 1px solid #E5E7EB;'>""", unsafe_allow_html=True)
                col_nama, col_status, col_opsi, col_crud = st.columns([3, 2, 2, 2])
                with col_nama:
                    st.write(f"**{idx+1}. {row['nama']}**")
                    st.caption(f"NISN: {row['nisn']} | WA: {row['no_wa_orang_tua']}")
                with col_status:
                    idx_default = ['hadir', 'sakit', 'tidak_hadir', 'belum'].index(status_clean)
                    status_phelan = st.radio(f"Status {row['nisn']}", ['hadir', 'sakit', 'tidak_hadir', 'belum'], index=idx_default, key=f"status_{row['nisn']}_{val_mapel}_{val_jam}", label_visibility="collapsed", horizontal=True)
                    if status_phelan != status_clean:
                        conn = get_db_connection()
                        c = conn.cursor()
                        c.execute('''INSERT OR REPLACE INTO absensi (nisn, tanggal, mapel, jam_ke, status, waktu, guru_input) VALUES (?, ?, ?, ?, ?, ?, ?)''', (row['nisn'], hari_ini, val_mapel, val_jam, status_phelan, datetime.datetime.now().strftime("%H:%M:%S"), st.session_state.username))
                        conn.commit()
                        conn.close()
                        st.rerun()
                with col_opsi:
                    if status_phelan == 'tidak_hadir':
                        url_wa = kirim_wa_link(row['no_wa_orang_tua'], row['nama'], pilihan_kelas, "Alpa", konteks_wa)
                        st.markdown(f"👉 [💬 Hubungi WA Ortu]({url_wa})")
                        catatan_lap = st.text_input("Catatan", key=f"catatan_{row['nisn']}_{val_mapel}_{val_jam}", placeholder="Tindak lanjut...", label_visibility="collapsed")
                        if st.button("Kirim ke Kepsek", key=f"btn_lap_{row['nisn']}_{val_mapel}_{val_jam}"):
                            conn = get_db_connection()
                            c = conn.cursor()
                            c.execute("INSERT INTO laporan_tindak_lanjut (nisn, tanggal, catatan, status_wa) VALUES (?, ?, ?, 'Sudah Dihubungi')", (row['nisn'], hari_ini, f"[{val_mapel}] {catatan_lap}"))
                            conn.commit()
                            conn.close()
                            st.success("Terkirim!")
                    elif status_phelan == 'hadir': st.write("✅ Hadir")
                    elif status_phelan == 'sakit': st.write("🤒 Sakit")
                    else: st.write("⏳ Belum Absen")
                    
                with col_crud:
                    with st.expander("⚙️ Kelola"):
                        with st.form(f"form_crud_siswa_{row['nisn']}"):
                            st.markdown("**Edit Informasi Siswa**")
                            e_nama_sis = st.text_input("Nama Siswa", value=row['nama'])
                            e_wa_sis = st.text_input("No WA Orang Tua", value=row['no_wa_orang_tua'])
                            e_kelas_sis = st.text_input("Kelas", value=row['kelas'])
                            check_hapus_sis = st.checkbox("Centang untuk menghapus siswa ini", key=f"del_sis_chk_{row['nisn']}")
                            col_btn1, col_btn2 = st.columns(2)
                            with col_btn1: btn_save_sis = st.form_submit_button("💾 Update")
                            with col_btn2: btn_del_sis = st.form_submit_button("🗑️ Hapus")
                            if btn_save_sis:
                                conn = get_db_connection()
                                c = conn.cursor()
                                c.execute("UPDATE siswa SET nama=?, no_wa_orang_tua=?, kelas=? WHERE nisn=?", (e_nama_sis, e_wa_sis, e_kelas_sis.strip().upper(), row['nisn']))
                                conn.commit()
                                conn.close()
                                st.success("Data siswa diperbarui!")
                                r_absen = st.rerun()
                            if btn_del_sis and check_hapus_sis:
                                conn = get_db_connection()
                                c = conn.cursor()
                                c.execute("DELETE FROM absensi WHERE nisn=?", (row['nisn'],))
                                c.execute("DELETE FROM laporan_tindak_lanjut WHERE nisn=?", (row['nisn'],))
                                c.execute("DELETE FROM siswa WHERE nisn=?", (row['nisn'],))
                                conn.commit()
                                conn.close()
                                st.success("Siswa dihapus!")
                                st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)