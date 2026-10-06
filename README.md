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
Settings, About ve onay pencereleri içerik yüksekliğine ve kullanılabilir ekran
alanına göre açılır. Settings geniş pencerelerde iki, dar pencerelerde tek sütun
kullanır. Küçük ekranlarda içerik kaydırılır; alt düğmeler görünür kalır.
About logosunun oranı ve tamamı korunur; yüksek ekran ölçeklerinde de uygun
çözünürlükte çizilir.
Metin alanının altındaki **Open** düğmesi UTF-8 (BOM dahil) veya UTF-16
kodlamalı `.txt` dosyalarını açar. Varsayılan maksimum birim sayısı **1.000.000**;
kabul kontrolü toplam normal boşluk (` `) sayısına dayanır. Karakter sınırı yoktur.
Ayarlar içindeki maksimum birim sayısı kalıcı olarak değiştirilebilir; 1 milyonun
üzerine çıkarılırken donanım kapasitesi için onay istenir. Kapasite kartındaki
1, 2 ve 5 milyon düğmeleri hızlı seçim sağlar; sayı alanına özel değer girilebilir.

Birimlendirmede tekrar eden kaynak birimler sınırlı bir önbellekten okunur;
paragraf bilgisi aynı geçişte oluşturulur. Metin değişmedikçe analiz belgesi yeniden
kullanılır. POS sonuçları son metin için önbelleğe alınır. Büyük POS girdileri,
modelin ara bellek kullanımını sınırlamak için yaklaşık 32.000 karakterlik
parçalarda işlenir; öncelikle cümle/satır, ardından boşluk sınırları seçilir.
Parça sınırlarındaki bağlam değişikliği POS etiketlerini etkileyebilir.

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

## Performans doğrulaması

Sonuç tablosunda birimlendirme, POS ve concordance kayıtları zaten kaynak
sırasındadır. Bu kayıtları yeniden sıralamak kaldırıldı; sıklık ve n-gram
sonuçlarında kullanıcı sıralaması korunur. Yeni sonuç yüklenmeden önce önceki
analizin sıralaması sıfırlanır; eski sütun üzerinden gereksiz sıralama yapılmaz.

Sıklık hesabında geçici birim listeleri azaltıldı. Tekrarlı girdilerde Türkçe
küçük harf dönüşümü tekil yüzey biçimleri üzerinde yapılır ve birleşen biçimlerin
sayıları toplanır. Çoğunlukla tekil girdiler küçük bir örnekle ayırt edilir ve
tek geçişli sayım kullanılır. Metin analizi özetinde birim türü ve tekil biçimler
tekrar hesaplanmaz. POS modeline, parça sınırlarına ve n-gram hesabına yeni bir
müdahale yapılmadı.

Geliştirme ortamında üç çalıştırmanın medyanı ile yapılan karşılaştırma:

| İşlem | Önce | Sonra |
| --- | ---: | ---: |
| 30.000 satırın tabloya aktarılması | 6,361 sn | 0,041 sn |
| 1.000.000 birimde sıklık hesabı | 0,419 sn | 0,185 sn |
| 1.000.000 birimde analiz özeti | 0,764 sn | 0,507 sn |

Bu sentetik ölçümlerde analiz belgesi önceden hazırlanmıştır; birimlendirme,
POS modeli, dosya okuma ve ekran boyama süreleri tabloya dahil değildir.
Başlıklar, tüm analiz satırları ve kopyalama metinleri önceki uygulamayla birebir
karşılaştırıldı. 100.000 tekil biçimde sıklık süresi yaklaşık 0,079 sn ile aynı
kaldı. Gerçek derlem ve donanıma göre süreler değişir.

Ölçümü tekrar çalıştırmak için:

```bash
python scripts/benchmark_performance.py --tokens 1000000 --table-rows 30000 --repeats 3 --output benchmark.json
python -m unittest discover -s tests
```

İsteğe bağlı `--reference-analysis` ve `--reference-window` seçenekleri, güvenilir
önceki `analysis_service.py` / `main_window.py` kopyalarıyla aynı girdileri
karşılaştırır; çıktı farklıysa ölçüm başarısız olur. Arayüz ölçümü geçici ayarlar
kullanır ve güncelleme isteği göndermez.

## Offline Çalışma

Uygulama çalışma sırasında model indirmez ve dependency kontrolü için internete bağlanmaz. Dağıtım paketinde Python runtime, TS Tokenizer, `ts-postagger`, PySide6 ve gerekli Python bağımlılıkları birlikte paketlenmelidir.

Sürüm denetimi açılıştan 3 saniye sonra ve uygulama açıkken her 6 saatte ayrı
bir arka plan iş parçacığında çalışır. Bağlantı hatasında 15 dakika sonra yeniden
dener. Otomatik kontrollerde bağlantı hatası pencere açmaz; aynı yeni sürüm için
uyarı bir kez gösterilir. Menüden **Sürümü Denetle** seçilince sonuç her zaman
bildirilir. Girilen metin bu denetime veya başka bir servise gönderilmez.

### Sürüm güncelleme kaynağı

[TS_TextLab deposu](https://github.com/tanerim/TS_TextLab) public olarak yayınlanır.
Sabit sürüm kaynağı, `master` dalındaki
[version.txt](https://raw.githubusercontent.com/tanerim/TS_TextLab/master/version.txt)
dosyasıdır. İlk açılışta ek ayar gerektirmeden bu adresten kontrol yapılır.
About penceresindeki **GitHub ↗** bağlantısı da aynı depoyu tarayıcıda açar.

Her dağıtımda yerel `version.txt` ile paket sürümünü belirleyin. Yeni paketi
kullanıcıların indirebileceği yerde yayınladıktan sonra depodaki `version.txt`
dosyasını güncelleyin. Eski kurulumlar yeni sürümü algılar ve kullanıcıya bildirir.
Bu dosya yalnızca `0.1.2` gibi bir kararlı sürüm numarası içerir; indirme düğmesi
olmadan sürüm bildirimi gösterilir.

Sürüm kaynağı kullanıcıdan adres girmesini istemeden otomatik kullanılır.
GitHub üzerindeki
[version.txt sayfasının](https://github.com/tanerim/TS_TextLab/blob/master/version.txt)
ham içeriği `https://raw.githubusercontent.com/tanerim/TS_TextLab/master/version.txt`
adresinden okunur. Ayarlarda güncelleme adresi alanı bulunmaz; önceki kayıtlı
adresler ve `TS_TEXTLAB_UPDATE_URL` ortam değişkeni kaynak seçimini etkilemez.
Menüdeki **Sürümü Denetle** aynı dosyayı elle kontrol eder. Uygulama güncellemeyi
bildirir; otomatik kurulum yapmaz. Boş/HTML/hatalı yanıtlar sürüm olarak kabul
edilmez. Paket `--self-test` kontrolü internete bağlanmaz.

## Linux, macOS ve Windows Dağıtımları

Üç platformun derleme ve paket testleri `.github/workflows/desktop-build.yml`
iş akışında çalışır. Her platform Python 3.13 ve `requirements-build.txt` ile
kendi işletim sisteminde derlenir. Paketlenmiş uygulama `--self-test` ile tüm
NLP işlevleri, CSV çıktıları, kaynaklar, iki dil, ayarlar, yardım ve hata sonrası
toparlanma açısından sınanır. Windows kurulum ve kaldırma, macOS disk imajından
çalıştırma testleri de yapılır. İş akışı yalnızca `master` üzerinden çalışır;
test sonuçları Git notes olarak saklanır, yeni branch oluşturulmaz.

Bu repo **public** olarak yayınlanır. Son kullanıcıya dağıtılacak `.exe` ve `.dmg`
dosyaları GitHub Releases veya herkese açık bir indirme sunucusunda yayınlanmalıdır.
Kullanıcıların GitHub hesabına veya Python kurulumuna ihtiyacı olmamalıdır.

Yerel derleme ve paket kontrolü:

```bash
python -m pip install -r requirements-build.txt
python -m PyInstaller packaging/ts_textlab.spec --clean --noconfirm
python scripts/check_distribution.py
# Windows/macOS üzerinde ayrıca:
python scripts/create_desktop_installer.py
```

Windows'ta `TS-TextLab-<sürüm>-windows-x86_64.exe` tek dosyadır:
indirip çift tıklamak uygulamayı açar, kurulum veya ZIP açma gerektirmez.
Model ve bağımlılıklar açılış sırasında geçici klasöre çıkartıldığı için
başlangıç klasör dağıtımına göre daha uzun sürebilir.
Alternatif olarak `TS-TextLab-<sürüm>-windows-x86_64-Setup.exe` kurulum dosyasıdır.
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
