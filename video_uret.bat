@echo off
:loop
echo [%TIME%] Video olusturma baslatiliyor...
:: Sanal ortamı aktif et ve kodu çalıştır
call .venv\Scripts\activate.bat
python run.py all

echo [%TIME%] Islem tamamlandi. 40 dakika bekleniyor...
:: 40 dakika = 2400 saniye (timeout saniye cinsinden çalışır)
timeout /t 2400

goto loop