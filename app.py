import os
import time
import re
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, flash
import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from groq import Groq

# Gizli .env dosyasındaki şifreleri otomatik yükler
load_dotenv()

# --- YAPAY ZEKA (AI) AYARLARI ---
# Şifreyi doğrudan .env dosyasından güvenli bir şekilde çeker
ai_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "super_gizli_anahtar")

# --- FOTOĞRAF YÜKLEME AYARLARI ---
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- BULUT UYUMLU VERİTABANI BAĞLANTISI ---
def get_db_connection():
    DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:135795@127.0.0.1/postgres")
    return psycopg2.connect(DATABASE_URL)

def update_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fit_users (
            id SERIAL PRIMARY KEY,
            kullanici_adi VARCHAR(50) UNIQUE NOT NULL,
            sifre VARCHAR(255) NOT NULL,
            rol VARCHAR(20) NOT NULL,
            paket VARCHAR(50) DEFAULT 'Standart',
            mesaj_hakki INTEGER DEFAULT 3,
            foto_hakki INTEGER DEFAULT 1,
            aktif_sohbet BOOLEAN DEFAULT FALSE,
            hak_yenilenme_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS antrenman_planlari (
            id SERIAL PRIMARY KEY,
            ogrenci_id INTEGER REFERENCES fit_users(id) ON DELETE CASCADE,
            hareket VARCHAR(100) NOT NULL,
            set_sayisi INTEGER NOT NULL,
            tekrar INTEGER NOT NULL,
            gun VARCHAR(50) NOT NULL,
            kardiyo VARCHAR(255),
            tamamlandi BOOLEAN DEFAULT FALSE
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS diyet_planlari (
            id SERIAL PRIMARY KEY,
            ogrenci_id INTEGER REFERENCES fit_users(id) ON DELETE CASCADE,
            ogun_adi VARCHAR(100) NOT NULL,
            icerik TEXT NOT NULL,
            kalori INTEGER DEFAULT 0,
            protein INTEGER DEFAULT 0,
            yag INTEGER DEFAULT 0,
            karbonhidrat INTEGER DEFAULT 0,
            gun VARCHAR(50) DEFAULT 'Hergün',
            tamamlandi BOOLEAN DEFAULT FALSE
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ogrenci_loglari (
            id SERIAL PRIMARY KEY,
            ogrenci_id INTEGER REFERENCES fit_users(id) ON DELETE CASCADE,
            hareket VARCHAR(100) NOT NULL,
            agirlik INTEGER NOT NULL,
            tekrar INTEGER NOT NULL,
            tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mesajlar (
            id SERIAL PRIMARY KEY,
            ogrenci_id INTEGER REFERENCES fit_users(id) ON DELETE CASCADE,
            mesaj TEXT NOT NULL,
            gonderen VARCHAR(20) DEFAULT 'ogrenci',
            tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fotograflar (
            id SERIAL PRIMARY KEY,
            ogrenci_id INTEGER REFERENCES fit_users(id) ON DELETE CASCADE,
            dosya_yolu VARCHAR(255) NOT NULL,
            tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kilo_takibi (
            id SERIAL PRIMARY KEY,
            ogrenci_id INTEGER REFERENCES fit_users(id) ON DELETE CASCADE,
            kilo NUMERIC(5,2) NOT NULL,
            tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    conn.commit()
    
    try: cursor.execute("ALTER TABLE mesajlar ADD COLUMN gonderen VARCHAR(20) DEFAULT 'ogrenci';"); conn.commit()
    except: conn.rollback()
    try: cursor.execute("ALTER TABLE diyet_planlari ADD COLUMN gun VARCHAR(50) DEFAULT 'Hergün';"); conn.commit()
    except: conn.rollback()
    try: cursor.execute("ALTER TABLE fit_users ADD COLUMN aktif_sohbet BOOLEAN DEFAULT FALSE;"); conn.commit()
    except: conn.rollback()
    try: cursor.execute("ALTER TABLE diyet_planlari ADD COLUMN yag INTEGER DEFAULT 0;"); conn.commit()
    except: conn.rollback()
    try: cursor.execute("ALTER TABLE diyet_planlari ADD COLUMN karbonhidrat INTEGER DEFAULT 0;"); conn.commit()
    except: conn.rollback()
    try: cursor.execute("ALTER TABLE fit_users ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE;"); conn.commit()
    except: conn.rollback()
    try: cursor.execute("ALTER TABLE fit_users ADD COLUMN deleted_at TIMESTAMP;"); conn.commit()
    except: conn.rollback()
    try: cursor.execute("ALTER TABLE antrenman_planlari ADD COLUMN tamamlandi BOOLEAN DEFAULT FALSE;"); conn.commit()
    except: conn.rollback()
    try: cursor.execute("ALTER TABLE diyet_planlari ADD COLUMN tamamlandi BOOLEAN DEFAULT FALSE;"); conn.commit()
    except: conn.rollback()
    # YENİ: Haftalık hak yenilenme tarihi sütunu
    try: cursor.execute("ALTER TABLE fit_users ADD COLUMN hak_yenilenme_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP;"); conn.commit()
    except: conn.rollback()
    
    cursor.close()
    conn.close()

update_database()

# --- KAYIT VE GİRİŞ İŞLEMLERİ ---
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        kullanici_adi = request.form.get("kullanici_adi")
        sifre = request.form.get("sifre")
        rol = "ogrenci" 
        hashed_sifre = generate_password_hash(sifre)
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO fit_users (kullanici_adi, sifre, rol) VALUES (%s, %s, %s)",
                           (kullanici_adi, hashed_sifre, rol))
            conn.commit()
            flash("Kayıt başarılı! Şimdi giriş yapabilirsiniz.", "success")
            return redirect(url_for("login"))
        except:
            conn.rollback()
            flash("Kullanıcı adı alınmış!", "danger")
        finally:
            cursor.close()
            conn.close()
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        kullanici_adi = request.form.get("kullanici_adi")
        sifre = request.form.get("sifre")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, sifre, rol FROM fit_users WHERE kullanici_adi = %s", (kullanici_adi,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user and check_password_hash(user[1], sifre):
            session["user_id"] = user[0]
            session["kullanici_adi"] = kullanici_adi
            session["rol"] = user[2]
            return redirect(url_for("ana_sayfa"))
        else:
            flash("Hatalı giriş!", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# --- ANA SAYFA (ANTRENÖR VE ÖĞRENCİ YÖNLENDİRMESİ) ---
@app.route("/", methods=["GET", "POST"])
def ana_sayfa():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    if session.get("rol") == "antrenor":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, kullanici_adi FROM fit_users WHERE rol = 'ogrenci' AND is_deleted = FALSE ORDER BY id DESC")  
        ogrenciler = [{"id": row[0], "kullanici_adi": row[1]} for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return render_template("antrenor_panel.html", ogrenciler=ogrenciler, hoca_adi=session.get("kullanici_adi"))
        
    else:
        conn = get_db_connection()
        cursor = conn.cursor()
        ogrenci_id = session.get("user_id")

        # YENİ: OTOMATİK HAFTALIK YENİLEME KONTROLÜ (7 gün geçtiyse hakları 3 ve 1 yap)
        cursor.execute("""
            UPDATE fit_users 
            SET mesaj_hakki = 3, foto_hakki = 1, hak_yenilenme_tarihi = CURRENT_TIMESTAMP 
            WHERE id = %s AND (hak_yenilenme_tarihi IS NULL OR hak_yenilenme_tarihi < NOW() - INTERVAL '7 days')
        """, (ogrenci_id,))
        conn.commit()

        cursor.execute("SELECT kullanici_adi, paket, mesaj_hakki, foto_hakki, aktif_sohbet FROM fit_users WHERE id = %s", (ogrenci_id,))
        kullanici_adi, paket, mesaj_hakki, foto_hakki, aktif_sohbet = cursor.fetchone()

        if request.method == "POST":
            form_tipi = request.form.get("form_tipi")

            if form_tipi == "mesaj_gonder":
                mesaj = request.form.get("mesaj")
                if aktif_sohbet:
                    cursor.execute("INSERT INTO mesajlar (ogrenci_id, mesaj, gonderen) VALUES (%s, %s, 'ogrenci')", (ogrenci_id, mesaj))
                    conn.commit()
                else:
                    if mesaj_hakki > 0:
                        cursor.execute("UPDATE fit_users SET mesaj_hakki = mesaj_hakki - 1, aktif_sohbet = TRUE WHERE id = %s", (ogrenci_id,))
                        cursor.execute("INSERT INTO mesajlar (ogrenci_id, mesaj, gonderen) VALUES (%s, %s, 'ogrenci')", (ogrenci_id, mesaj))
                        conn.commit()
                    else:
                        flash("Haftalık soru hakkınız dolmuştur!", "danger")

            elif form_tipi == "foto_yukle":
                if foto_hakki > 0:
                    foto = request.files.get("foto")
                    if foto and foto.filename != '':
                        dosya_adi = secure_filename(foto.filename)
                        yeni_dosya_adi = f"ogrenci_{ogrenci_id}_{dosya_adi}"
                        foto.save(os.path.join(app.config['UPLOAD_FOLDER'], yeni_dosya_adi))
                        cursor.execute("INSERT INTO fotograflar (ogrenci_id, dosya_yolu) VALUES (%s, %s)", (ogrenci_id, yeni_dosya_adi))
                        cursor.execute("UPDATE fit_users SET foto_hakki = foto_hakki - 1 WHERE id = %s", (ogrenci_id,))
                        conn.commit()
                        flash("Form fotoğrafı yüklendi!", "success")
                else:
                    flash("Fotoğraf yükleme hakkınız dolmuştur!", "danger")

            elif form_tipi == "kilo_ekle":
                kilo = request.form.get("kilo")
                if kilo:
                    kilo_temiz = float(kilo.replace(',', '.'))
                    cursor.execute("INSERT INTO kilo_takibi (ogrenci_id, kilo) VALUES (%s, %s)", (ogrenci_id, kilo_temiz))
                    conn.commit()
                    flash(f"Güncel kilonuz ({kilo_temiz} kg) kaydedildi!", "success")

            return redirect(url_for("ana_sayfa"))

        cursor.execute("SELECT gun, hareket, set_sayisi, tekrar, kardiyo, id, tamamlandi FROM antrenman_planlari WHERE ogrenci_id = %s ORDER BY id ASC", (ogrenci_id,))
        antrenmanlar = cursor.fetchall()
        
        cursor.execute("SELECT gun, ogun_adi, icerik, kalori, protein, yag, karbonhidrat, id, tamamlandi FROM diyet_planlari WHERE ogrenci_id = %s ORDER BY id ASC", (ogrenci_id,))
        diyetler = cursor.fetchall()
        
        cursor.execute("SELECT mesaj, gonderen, tarih FROM mesajlar WHERE ogrenci_id = %s ORDER BY id ASC", (ogrenci_id,))
        mesajlar = cursor.fetchall()
        
        cursor.execute("SELECT kilo, tarih FROM kilo_takibi WHERE ogrenci_id = %s ORDER BY tarih ASC", (ogrenci_id,))
        kilo_kayitlari = cursor.fetchall()
        kilo_tarihler = [row[1].strftime('%d.%m') for row in kilo_kayitlari]
        kilo_degerler = [float(row[0]) for row in kilo_kayitlari]

        cursor.close()
        conn.close()
        hafta = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        
        return render_template("ogrenci_panel.html", 
                               ogrenci_adi=kullanici_adi, paket=paket, mesaj_hakki=mesaj_hakki, foto_hakki=foto_hakki, aktif_sohbet=aktif_sohbet,
                               antrenmanlar=antrenmanlar, diyetler=diyetler, mesajlar=mesajlar, hafta=hafta,
                               kilo_tarihler=kilo_tarihler, kilo_degerler=kilo_degerler)

# --- ÖĞRENCİ GÖREV TAMAMLAMA (CHECK-OFF) ROTASI ---
@app.route("/gorev_durum/<tip>/<int:item_id>", methods=["POST"])
def gorev_durum(tip, item_id):
    if "user_id" not in session: return redirect(url_for("login"))
    conn = get_db_connection()
    cursor = conn.cursor()
    ogrenci_id = session.get("user_id")
    
    if tip == "antrenman":
        cursor.execute("UPDATE antrenman_planlari SET tamamlandi = NOT tamamlandi WHERE id = %s AND ogrenci_id = %s", (item_id, ogrenci_id))
    elif tip == "diyet":
        cursor.execute("UPDATE diyet_planlari SET tamamlandi = NOT tamamlandi WHERE id = %s AND ogrenci_id = %s", (item_id, ogrenci_id))
        
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for("ana_sayfa"))

# --- ANTRENÖR: HAFTALIK PLAN YAZMA & AI BAĞLANTISI ---
@app.route("/haftalik_plan/<int:ogrenci_id>", methods=["GET", "POST"])
def haftalik_plan(ogrenci_id):
    if session.get("rol") != "antrenor": return redirect(url_for("ana_sayfa"))
    conn = get_db_connection(); cursor = conn.cursor()
    
    if request.method == "POST":
        form_tipi = request.form.get("form_tipi")
        gun = request.form.get("gun")
        
        if form_tipi == "antrenman":
            hareket = request.form.get("hareket")
            set_s = request.form.get("set_sayisi")
            tekrar = request.form.get("tekrar")
            kardiyo = request.form.get("kardiyo")
            
            if not hareket:
                hareket = "🏃‍♂️ Sadece Kardiyo"
                set_s = 0
                tekrar = 0
                
            cursor.execute("INSERT INTO antrenman_planlari (ogrenci_id, hareket, set_sayisi, tekrar, gun, kardiyo) VALUES (%s, %s, %s, %s, %s, %s)", (ogrenci_id, hareket, set_s, tekrar, gun, kardiyo))
            conn.commit()
            flash(f"{gun} gününe antrenman eklendi!", "success")
            
        elif form_tipi == "diyet_ai":
            ogun = request.form.get("ogun_adi")
            icerik = request.form.get("icerik")
            
            basarili_mi = False
            
            for deneme in range(3):
                try:
                    prompt = f"Şu içerikteki yiyeceklerin besin değerlerini tek tek düşün, topla ve EN SON satıra sadece toplamları şu formatta yaz: \nTOPLAM: Kalori, Protein, Yağ, Karbonhidrat \nİçerik: '{icerik}'"
                    
                    response = ai_client.chat.completions.create(
                        messages=[{"role": "user", "content": prompt}],
                        model="qwen/qwen3.8-27b" 
                    )
                    
                    cevap_metni = response.choices[0].message.content
                    print(f"\n--- AI CEVABI (Deneme {deneme+1}) ---:\n{cevap_metni}")
                    
                    if "TOPLAM:" in cevap_metni:
                        son_kisim = cevap_metni.split("TOPLAM:")[-1]
                    else:
                        son_kisim = cevap_metni
                        
                    sayilar = re.findall(r'\d+[\.\,]?\d*', son_kisim)
                    
                    if len(sayilar) >= 4:
                        kalori = int(float(sayilar[-4].replace(',', '.')))
                        protein = int(float(sayilar[-3].replace(',', '.')))
                        yag = int(float(sayilar[-2].replace(',', '.')))
                        karb = int(float(sayilar[-1].replace(',', '.')))
                        
                        flash(f"Yapay Zeka başarıyla hesapladı! ({kalori} kcal)", "success")
                        basarili_mi = True
                        break
                    else:
                        raise ValueError(f"Yeterli rakam dönmedi! Gelen: {cevap_metni}")
                        
                except Exception as e:
                    print(f"Deneme {deneme + 1} başarısız: {str(e)}")
                    time.sleep(2)
            
            if not basarili_mi:
                kalori, protein, yag, karb = 0, 0, 0, 0
                flash("Hesaplamada sorun oluştu, lütfen manuel kontrol edin.", "danger")
                
            cursor.execute("INSERT INTO diyet_planlari (ogrenci_id, ogun_adi, icerik, kalori, protein, yag, karbonhidrat, gun) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", (ogrenci_id, ogun, icerik, kalori, protein, yag, karb, gun))
            conn.commit()
            
        return redirect(url_for("haftalik_plan", ogrenci_id=ogrenci_id))
        
    cursor.execute("SELECT kullanici_adi FROM fit_users WHERE id = %s", (ogrenci_id,))
    ogrenci = cursor.fetchone()
    cursor.execute("SELECT gun, hareket, set_sayisi, tekrar, kardiyo, id, tamamlandi FROM antrenman_planlari WHERE ogrenci_id = %s ORDER BY id ASC", (ogrenci_id,))
    antrenmanlar = cursor.fetchall()
    cursor.execute("SELECT gun, ogun_adi, icerik, kalori, protein, yag, karbonhidrat, id, tamamlandi FROM diyet_planlari WHERE ogrenci_id = %s ORDER BY id ASC", (ogrenci_id,))
    diyetler = cursor.fetchall()
    cursor.close(); conn.close()
    
    hafta = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
    return render_template("haftalik_plan.html", ogrenci=ogrenci, hafta=hafta, antrenmanlar=antrenmanlar, diyetler=diyetler, ogrenci_id=ogrenci_id)

# --- ANTRENÖR: ÖĞRENCİ DETAY, GELEN KUTUSU VE GRAFİK ---
@app.route("/ogrenci_detay/<int:ogrenci_id>", methods=["GET", "POST"])
def ogrenci_detay(ogrenci_id):
    if session.get("rol") != "antrenor": return redirect(url_for("ana_sayfa"))
    conn = get_db_connection(); cursor = conn.cursor()

    if request.method == "POST":
        mesaj = request.form.get("mesaj")
        cursor.execute("INSERT INTO mesajlar (ogrenci_id, mesaj, gonderen) VALUES (%s, %s, 'antrenor')", (ogrenci_id, mesaj))
        conn.commit()
        return redirect(url_for("ogrenci_detay", ogrenci_id=ogrenci_id))
    
    # Öğrencinin kalan haklarını da çekiyoruz (ogrenci[2] = mesaj_hakki, ogrenci[3] = foto_hakki)
    cursor.execute("SELECT kullanici_adi, aktif_sohbet, mesaj_hakki, foto_hakki FROM fit_users WHERE id = %s", (ogrenci_id,))
    ogrenci = cursor.fetchone()
    cursor.execute("SELECT mesaj, gonderen, tarih FROM mesajlar WHERE ogrenci_id = %s ORDER BY id ASC", (ogrenci_id,))
    mesajlar = cursor.fetchall()
    cursor.execute("SELECT dosya_yolu, tarih FROM fotograflar WHERE ogrenci_id = %s ORDER BY id DESC", (ogrenci_id,))
    fotograflar = cursor.fetchall()
    
    cursor.execute("SELECT kilo, tarih FROM kilo_takibi WHERE ogrenci_id = %s ORDER BY tarih ASC", (ogrenci_id,))
    kilo_kayitlari = cursor.fetchall()
    kilo_tarihler = [row[1].strftime('%d.%m') for row in kilo_kayitlari]
    kilo_degerler = [float(row[0]) for row in kilo_kayitlari]
    
    cursor.close(); conn.close()
    return render_template("ogrenci_detay.html", 
                           ogrenci=ogrenci, mesajlar=mesajlar, fotograflar=fotograflar, ogrenci_id=ogrenci_id,
                           kilo_tarihler=kilo_tarihler, kilo_degerler=kilo_degerler)

# --- YENİ: ANTRENÖR MANUEL HAK SIFIRLAMA / YENİLEME ROTASI ---
@app.route("/haklari_yenile/<int:ogrenci_id>", methods=["POST"])
def haklari_yenile(ogrenci_id):
    if session.get("rol") != "antrenor": return redirect(url_for("ana_sayfa"))
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("""
        UPDATE fit_users 
        SET mesaj_hakki = 3, foto_hakki = 1, hak_yenilenme_tarihi = CURRENT_TIMESTAMP 
        WHERE id = %s
    """, (ogrenci_id,))
    conn.commit(); cursor.close(); conn.close()
    flash("Öğrencinin haftalık soru (3) ve fotoğraf (1) hakları başarıyla yenilendi!", "success")
    return redirect(url_for("ogrenci_detay", ogrenci_id=ogrenci_id))

# --- ANTRENÖR: SOHBETİ SONLANDIRMA ---
@app.route("/sohbet_sonlandir/<int:ogrenci_id>", methods=["POST"])
def sohbet_sonlandir(ogrenci_id):
    if session.get("rol") != "antrenor": return redirect(url_for("ana_sayfa"))
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("UPDATE fit_users SET aktif_sohbet = FALSE WHERE id = %s", (ogrenci_id,))
    conn.commit(); cursor.close(); conn.close()
    flash("Sohbet başarıyla sonlandırıldı. Öğrencinin bir sonraki mesajında hesabından 1 soru hakkı düşülecektir.", "info")
    return redirect(url_for("ogrenci_detay", ogrenci_id=ogrenci_id))

# --- ANTRENÖR: ÖĞRENCİ YUMUŞAK SİLME ---
@app.route("/ogrenci_sil/<int:ogrenci_id>", methods=["POST"])
def ogrenci_sil(ogrenci_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE fit_users SET is_deleted = TRUE, deleted_at = CURRENT_TIMESTAMP WHERE id = %s", (ogrenci_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Öğrenci çöp kutusuna taşındı. 7 gün içinde geri alabilirsiniz.", "warning")
    return redirect(url_for("ana_sayfa"))

# --- ANTRENÖR: PLAN SİLME ---
@app.route("/plan_sil/<tip>/<int:item_id>", methods=["POST"])
def plan_sil(tip, item_id):
    if session.get("rol") != "antrenor": return redirect(url_for("ana_sayfa"))
    ogrenci_id = request.form.get("ogrenci_id")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if tip == "antrenman":
        cursor.execute("DELETE FROM antrenman_planlari WHERE id = %s", (item_id,))
    elif tip == "diyet":
        cursor.execute("DELETE FROM diyet_planlari WHERE id = %s", (item_id,))
        
    conn.commit()
    cursor.close()
    conn.close()
    flash("Kayıt başarıyla silindi!", "info")
    return redirect(url_for("haftalik_plan", ogrenci_id=ogrenci_id))

# --- ANTRENÖR: PLAN DÜZENLEME ---
@app.route("/plan_duzenle/<tip>/<int:item_id>", methods=["POST"])
def plan_duzenle(tip, item_id):
    if session.get("rol") != "antrenor": return redirect(url_for("ana_sayfa"))
    ogrenci_id = request.form.get("ogrenci_id")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if tip == "antrenman":
        hareket = request.form.get("hareket")
        set_s = request.form.get("set_sayisi")
        tekrar = request.form.get("tekrar")
        kardiyo = request.form.get("kardiyo")
        cursor.execute("UPDATE antrenman_planlari SET hareket=%s, set_sayisi=%s, tekrar=%s, kardiyo=%s WHERE id=%s", (hareket, set_s, tekrar, kardiyo, item_id))
        flash("Antrenman başarıyla güncellendi!", "success")
        
    elif tip == "diyet":
        ogun = request.form.get("ogun_adi")
        icerik = request.form.get("icerik")
        kalori = request.form.get("kalori")
        protein = request.form.get("protein")
        yag = request.form.get("yag")
        karb = request.form.get("karbonhidrat")
        cursor.execute("UPDATE diyet_planlari SET ogun_adi=%s, icerik=%s, kalori=%s, protein=%s, yag=%s, karbonhidrat=%s WHERE id=%s", (ogun, icerik, kalori, protein, yag, karb, item_id))
        flash("Öğün başarıyla güncellendi!", "success")
        
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for("haftalik_plan", ogrenci_id=ogrenci_id))

# --- ANTRENÖR: ÇÖP KUTUSU VE 7 GÜN TEMİZLİĞİ ---
@app.route("/cop_kutusu")
def cop_kutusu():
    if session.get("rol") != "antrenor": return redirect(url_for("ana_sayfa"))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM fit_users WHERE is_deleted = TRUE AND deleted_at < NOW() - INTERVAL '7 days'")
    conn.commit()
    
    cursor.execute("SELECT id, kullanici_adi, deleted_at FROM fit_users WHERE rol = 'ogrenci' AND is_deleted = TRUE ORDER BY deleted_at DESC")
    silinen_ogrenciler = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template("cop_kutusu.html", ogrenciler=silinen_ogrenciler)

# --- ANTRENÖR: ÖĞRENCİ KURTARMA ---
@app.route("/ogrenci_kurtar/<int:ogrenci_id>", methods=["POST"])
def ogrenci_kurtar(ogrenci_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE fit_users SET is_deleted = FALSE, deleted_at = NULL WHERE id = %s", (ogrenci_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Öğrenci başarıyla kurtarıldı!", "success")
    return redirect(url_for("cop_kutusu"))

if __name__ == "__main__":
    app.run(debug=True)