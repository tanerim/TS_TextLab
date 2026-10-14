TS TextLab 0.1.3

- Sıklık hesabı artık hashtag, emoji ve noktalama dahil tüm tokenizer birimlerini sayar. Harf duyarsız modda metin, tokenizasyon öncesinde TS Tokenizer'ın Türkçe küçük harf fonksiyonuyla dönüştürülür.
- Tablo numaraları en az beş basamak gösterebilir; sayısal hücreler sola yaslıdır.
- Tüm tablolarda − / + düğmeleriyle yazı boyutu değiştirilebilir. Seçilen boyut kaydedilir.
- Filtre temizleme ikonunun ve üst bardaki seçili araç etiketinin yerleşimi düzeltildi.

İndirip kullanmak için Python veya GitHub hesabı gerekmez:

- Windows x86_64: `TS-TextLab-windows-x86_64-Setup.exe` ile kurun veya `TS-TextLab-windows-x86_64.exe` taşınabilir uygulamasını açın.
- macOS Apple Silicon: DMG'yi açıp uygulamayı Applications / Uygulamalar klasörüne sürükleyin. Intel Mac paketi içermez.
- Linux x86_64: `.tar.gz` arşivini açıp TS TextLab dosyasını çalıştırın; `_internal` klasörünü yanında tutun. Ubuntu 24.04 üzerinde derlenir ve sınanır.

İmzasız Windows paketleri SmartScreen uyarısı gösterebilir. `-unsigned.dmg` paketi Apple Developer ID imzası ve noter onayı taşımaz; macOS ilk açılışı engelleyebilir.

Dosyaların SHA-256 değerleri `SHA256SUMS.txt` içinde yer alır. Yayın yalnızca üç platformun birim testleri, uygulama kontrolleri ve paket kontrolleri başarılı olduğunda oluşturulur.
