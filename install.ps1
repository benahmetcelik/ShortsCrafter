# Sadece Python 3.11 veya üstü ile çalışmasını sağla (istersen 3.11 yolunu buraya yazabilirsin)
$pythonPath = "python" 

Write-Host "Sanal ortam oluşturuluyor..." -ForegroundColor Cyan
& $pythonPath -m venv .venv

Write-Host "Sanal ortam aktif ediliyor..." -ForegroundColor Cyan
.\.venv\Scripts\Activate.ps1

Write-Host "Paketler yükleniyor..." -ForegroundColor Cyan
.\.venv\Scripts\pip install --upgrade pip
.\.venv\Scripts\pip install -r requirements.txt

Write-Host "Kurulum başarıyla tamamlandı!" -ForegroundColor Green