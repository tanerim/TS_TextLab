# TS TextLab

TS TextLab, Türkçe metinler üzerinde TS Tokenizer ve
`ts-postagger` paketindeki spaCy tabanlı TS POSTagger modeliyle çalışan offline masaüstü uygulamasıdır.

## PyCharm Geliştirme Kurulumu

1. PyCharm'da bu klasörü proje olarak açın.
2. Python 3.10, 3.11, 3.12 veya 3.13 ile virtual environment oluşturun.
3. Bağımlılıkları kurun:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Not: POS modeli `ts-postagger` paketiyle birlikte gelir.
Modeli güncellemek için paketi güncellemeniz yeterlidir.

## GUI Çalıştırma

```bash
python -X utf8 main.py
```

Arayüz sistem yereli Türkçe ise Türkçe,
diğer durumlarda İngilizce açılır.
Settings menüsünden dil tercihi kalıcı olarak değiştirilebilir.
Tokenization Mode için `tokenized`, `tagged` ve `lines` çıktı modları seçilebilir.

Sonuçlar **CSV'ye Aktar** ile UTF-8 kodlamasında, tab (`\t`) ile ayrılmış `.csv`
dosyalarına kaydedilir. Başlıklar ve tüm analiz satırları dışa aktarılır;
arayüzdeki filtre dosyanın içeriğini daraltmaz. NLP iş akışlarında tutarlı olması
için sütun başlıkları arayüz dilinden bağımsızdır. Metin Analizi çıktısı da
ölçümler ve dağılımlar için aynı tablo biçimini kullanır.
Dosya adına yerel tarih, saat ve mikrosaniye eklenir:
`ts-textlab-frequency-20261006-143025-123456.csv`.

`lines` modu çok satırlı metinlerde satır ayrımını korur.
`tagged` modu tokenizer etiketlerini gösterir; bu etiketler sözcük türü etiketi değildir,
verilen dizgenin işlevini tanımlar. POSTag işlemi öncesinde metin TS Tokenizer'dan geçirilir;
böylece tokenizer'ın karakter düzeltme ve token sınırı çıktısı POS modeline uygulanır.

## GUI Olmadan Test

```bash
python scripts/smoke_test.py
```

## Offline Çalışma

Uygulama çalışma sırasında model indirmez ve dependency kontrolü için internete bağlanmaz. Dağıtım paketinde Python runtime, TS Tokenizer, `ts-postagger`, PySide6 ve gerekli Python bağımlılıkları birlikte paketlenmelidir.

Başlangıçta kısa timeout ile public repo kökündeki `version.txt` dosyasının raw GitHub adresinden sürüm denetimi yapılır. Bağlantı yoksa hata kullanıcıya gösterilmez; dosya mevcut sürümden yeni bir değer dönerse güncelleme uyarısı gösterilir. Girilen metin bu denetime veya başka bir servise gönderilmez.

## Linux, macOS ve Windows Dağıtımları

Üç platformun derleme ve paket testleri `.github/workflows/desktop-build.yml`
iş akışında çalışır. Her platform Python 3.13 ve `requirements-build.txt` ile
kendi işletim sisteminde derlenir. Paketlenmiş uygulama `--self-test` ile tüm
NLP işlevleri, CSV çıktıları, kaynaklar, iki dil, ayarlar, yardım ve hata sonrası
toparlanma açısından sınanır. Windows kurulum ve kaldırma, macOS disk imajından
çalıştırma testleri de yapılır. İş akışı yalnızca `master` üzerinden çalışır;
test sonuçları Git notes olarak saklanır, yeni branch oluşturulmaz.

Bu repo **private** olduğu için Actions çıktıları yalnızca geliştirici içindir.
Son kullanıcıya dağıtılacak `.exe` ve `.dmg` dosyaları, herkese açık bir indirme
sunucusuna yüklenmelidir. Kullanıcıların GitHub hesabına veya Python kurulumuna
ihtiyacı olmamalıdır.

Yerel derleme ve paket kontrolü:

```bash
python -m pip install -r requirements-build.txt
python -m PyInstaller packaging/ts_textlab.spec --clean --noconfirm
python scripts/check_distribution.py
# Windows/macOS üzerinde ayrıca:
python scripts/create_desktop_installer.py
```

Windows dağıtımı `TS-TextLab-<sürüm>-windows-x86_64-Setup.exe` dosyasıdır.
Kullanıcı çift tıklayarak kurar; Başlat menüsü ve masaüstü kısayolundan uygulamayı
açar. Kurulum kullanıcı hesabına yapılır, yönetici yetkisi veya Python istemez.
Kurulum aracı Inno Setup 6'dır.

macOS dağıtımı `.dmg` dosyasıdır. Kullanıcı çift tıklayarak açar, TS TextLab'ı
Applications'a sürükler ve uygulamayı çift tıklayarak çalıştırır. ARM64 paketi
Apple Silicon içindir. İmzasız test imajlarının adında `-unsigned` bulunur.
İnternetten indirilen bir uygulamanın Gatekeeper tarafından kabul edilmesi için
Developer ID imzası ve Apple notarization gereklidir. Bunlar olmadan normal
indir/çift tıkla/çalıştır deneyimi tamamlanmış sayılmaz.

Linux çıktısı `.tar.gz` arşividir. Paket adları sürümü, işletim sistemini ve işlemci mimarisini içerir.
Linux'ta arşivi kalıcı bir klasöre açıp `install-linux.sh` betiğini çalıştırmak,
TS Corpus simgesiyle uygulama menüsüne kısayol ekler. Betik yönetici yetkisi istemez.
Uygulamanın sürümü `version.txt` üzerinden okunur; paketleme aynı dosyayı içerir.

Windows çıktısı `dist/TS TextLab/TS TextLab.exe`, Linux çıktısı
`dist/TS TextLab/TS TextLab`, macOS çıktısı `dist/TS TextLab.app` altında oluşur.
Paketlenmiş uygulamalar, tokenizer veri dosyalarının Windows'ta da doğru
okunması için UTF-8 modunda başlar.

macOS imzalama kurulumu için [dağıtım notlarına](packaging/DISTRIBUTION.md) bakın.

## Dosya Yapısı

```text
app/
  main_window.py          # PySide6 kullanıcı arayüzü
  tokenizer_service.py    # TS Tokenizer kütüphanesi
  postagger_service.py    # TS Postagger kütüphanesi ve POS tagging
  resource_manager.py     # dev/build resource yolları
  logging_config.py       # log kurulumu
main.py                   # uygulama giriş noktası
version.txt               # public repo üzerinden okunan son sürüm değeri
scripts/smoke_test.py     # GUI'siz NLP doğrulaması
packaging/ts_textlab.spec # PyInstaller ayarları
```

## Kaynak

TS Tokenizer PyPI dokümantasyonu paket adını `ts-tokenizer`,
import adını `ts_tokenizer`,
Python gereksinimini 3.9+ ve çıktı modlarını `tokenized`, `tagged`, `lines`, `tagged_lines` olarak listeler:
https://pypi.org/project/ts-tokenizer/

TS POSTagger PyPI paketi `ts-postagger`,
import adı `ts_postagger` ve Python gereksinimi 3.11+ olan paketli POS modelini sağlar:
https://pypi.org/project/ts-postagger/
