# TS TextLab

**TS TextLab, Türkçe metinleri incelemek için hazırlanmış bir masaüstü uygulamasıdır.** Metninizi açıp sözcüklere ve diğer metin birimlerine ayırabilir, sözcük türlerini etiketleyebilir, sıklık listeleri çıkarabilir ve sözcüklerin hangi bağlamlarda kullanıldığını görebilirsiniz. Dil araştırmaları, ders çalışmaları ve metin incelemelerinde kullanılabilir; hazır paketlerle kullanmak için kod yazmanız veya Python kurmanız gerekmez.

Uygulama [TS Tokenizer](https://pypi.org/project/ts-tokenizer/) ve [TS POSTagger](https://pypi.org/project/ts-postagger/) kullanır. Buradaki **birim**, bir sözcük, noktalama işareti, internet adresi veya metindeki başka bir öğe olabilir; birim sayısı her zaman sözcük sayısıyla aynı değildir.

Metinler bilgisayarınızda işlenir ve başka bir servise gönderilmez. Analizler internet olmadan çalışır. İnternet bağlantısı yalnızca yeni sürüm kontrolü ve açtığınız dış bağlantılar için kullanılır.

## İndir ve çalıştır

**Güncel paket sürümü: 0.1.1.** GitHub hesabı veya Python kurulumu gerekmez. İşletim sisteminize uygun paketi doğrudan indirebilirsiniz:

| İşletim sistemi | İndirme bağlantısı | Paket |
| --- | --- | --- |
| Windows — Intel/AMD 64 bit | [Kurulum paketini indir](https://github.com/tanerim/TS_TextLab/releases/download/v0.1.1/TS-TextLab-windows-x86_64-Setup.exe) | Önerilen kurulum paketi |
| Windows — Intel/AMD 64 bit | [Taşınabilir sürümü indir](https://github.com/tanerim/TS_TextLab/releases/download/v0.1.1/TS-TextLab-windows-x86_64.exe) | Kurulum gerektirmeyen taşınabilir sürüm |
| macOS — Apple Silicon (M serisi) | [macOS paketini indir](https://github.com/tanerim/TS_TextLab/releases/download/v0.1.1/TS-TextLab-macos-arm64-unsigned.dmg) | DMG disk imajı |
| Linux — Intel/AMD 64 bit | [Linux paketini indir](https://github.com/tanerim/TS_TextLab/releases/download/v0.1.1/TS-TextLab-linux-x86_64.tar.gz) | TAR.GZ uygulama arşivi |


Tüm yayımlanmış sürümler [Releases](https://github.com/tanerim/TS_TextLab/releases) sayfasında yer alır. Yukarıdaki bağlantılar en güncel sürümün dosyalarına gider.

### Windows

1. İndirilen ZIP dosyasını açın.
2. Kurulum yapmadan kullanmak için `TS-TextLab-0.1.1-windows-x86_64.exe` dosyasına çift tıklayın.
3. Kurulum ve kısayollar için `TS-TextLab-0.1.1-windows-x86_64-Setup.exe` dosyasını açıp adımları izleyin. Ardından uygulamayı Başlat menüsünden veya masaüstü kısayolundan açabilirsiniz.

Python kurulumu gerekmez. Taşınabilir uygulamanın ilk açılışı, içerdiği model hazırlanırken biraz uzun sürebilir. Paket imzasız olduğu için Windows SmartScreen uyarısı gösterebilir.

### macOS

1. İndirilen ZIP dosyasını açın.
2. `.dmg` dosyasına çift tıklayın.
3. **TS TextLab** uygulamasını **Applications / Uygulamalar** klasörüne sürükleyin.
4. Uygulamayı bu klasörden açın.

Mevcut paket **Apple Silicon içindir; Intel Mac paketi yoktur**. Dosya adındaki `-unsigned`, paketin Apple geliştirici imzası ve noter onayı taşımadığını belirtir. macOS bu paketi engelleyebilir; mevcut sürüm her Mac'te uyarısız çift tıklamayla açılacak bir dağıtım değildir.

### Linux

1. İndirilen ZIP dosyasını, ardından içindeki `.tar.gz` arşivini açın.
2. Oluşan **TS TextLab** klasörünü kalıcı olarak tutacağınız bir yere taşıyın.
3. Klasördeki **TS TextLab** çalıştırılabilir dosyasına çift tıklayın. `_internal` klasörü uygulamayla birlikte kalmalıdır.

İsterseniz aynı klasördeki `install-linux.sh` betiğini çalıştırarak uygulama menüsüne kısayol ekleyebilirsiniz; yönetici yetkisi gerekmez. Linux paketi Ubuntu 24.04 üzerinde hazırlanmıştır; tüm Linux dağıtımlarında uyumluluk doğrulanmamıştır. Dosya yöneticiniz çalıştırma izni isterse dosyanın özelliklerinden bu izni etkinleştirin.

## Kullanma kılavuzu

### İlk analizinizi yapın

1. Kaynak metin alanına Türkçe metninizi yazın veya yapıştırın. Bir dosya kullanmak için alanın altındaki **Open / Aç** düğmesinden `.txt` dosyasını seçin. UTF-8 ve UTF-16 metin dosyaları desteklenir.
2. Üstteki sekmelerden yapmak istediğiniz işlemi seçin.
3. Seçenekleri düzenleyip işlem düğmesine basın. **Metin Analizi** sekmesi seçildiğinde işlem otomatik başlar.
4. Sonuçları inceleyin; gerekirse filtreleyin, kopyalayın veya dosyaya aktarın.

Örneğin, “Bugün güzel bir gün. Yarın da güzel olacak.” metnini yapıştırıp **Sıklık** işlemini çalıştırdığınızda “güzel” biriminin iki kez geçtiğini görebilirsiniz. Bu birimin satırına tıklayıp **Concordance** ile metindeki kullanımlarını bağlamlarıyla inceleyebilirsiniz.

İşlem sırasında hareketli ilerleme çubuğu görünür. Bu çubuk işlemin sürdüğünü gösterir; yüzde veya kalan süre tahmini vermez. Sonuçların üstündeki bilgi alanında işlenen kayıt sayısı ve geçen süre yer alır. Büyük metinler ve sözcük türü etiketleme daha uzun sürebilir.

### Birimlendirme

**Birimlendirme**, metni sözcük, noktalama ve diğer metin birimlerine ayırır. Mod seçip **Birimlendir** düğmesine basın.

| Mod | Ne gösterir? |
| --- | --- |
| Birimlendirilmiş (`tokenized`) | Her birimi ayrı bir satırda gösterir. |
| Etiketli Birimlendirme (`tagged`) | Birimi ve tokenizer etiketini birlikte gösterir. |
| Satır Yapısını Koru (`lines`) | Kaynak metnin boş olmayan satırlarını birimlendirilmiş içerikleriyle gösterir. |

`URL`, `Hashtag` veya `Punctuation` gibi etiketler birimin metindeki işlevini belirtir. **Bunlar sözcük türü etiketi değildir.** İsim, fiil veya sıfat gibi türler için Sözcük Türü Etiketleme sekmesini kullanın.

### Sözcük türü etiketleme

Bu işlem, birimlere bağlama göre dilbilgisel tür atar. Çıktı biçimini seçip **Sözcük Türü Etiketle** düğmesine basın.

- **Full:** Birim, küçük harf biçimi ve POS etiketi gösterilir.
- **Tag:** Birim ve POS etiketi gösterilir.

Örneğin `Noun` isim, `Verb` fiil, `Adj` sıfat anlamına gelir. İlk çalıştırmada modelin hazırlanması biraz daha uzun sürebilir. Etiketler otomatik model tahminleridir; araştırmanızda önemli örnekleri bağlamıyla kontrol edin.

### Sıklık

**Sıklık**, sözcük benzeri birimlerin metinde kaç kez geçtiğini sayar. Noktalama gibi sözlüksel olmayan birimler bu hesaba katılmaz.

- **Harf duyarsız:** Büyük/küçük harf biçimleri Türkçeye uygun küçük harf dönüşümüyle birleştirilir.
- **Harf duyarlı:** Farklı büyük/küçük harf biçimleri ayrı sayılır.

Sonuçlar en yüksek sıklıktan başlayarak gösterilir. Sütun başlığına tıklayarak sıralamayı değiştirebilirsiniz. Bir satıra tıklamak o birimi Concordance arama alanına taşır.

### N-gramlar

**N-gram**, art arda gelen birimlerin oluşturduğu gruptur. `n` listesinden **2, 3, 4 veya 5** seçin. Örneğin “güzel bir gün” ifadesinde ikili gruplar “güzel bir” ve “bir gün”; üçlü grup “güzel bir gün” olur.

Varsayılan olarak yalnızca **Sözcükler** seçilidir. İlgili kutuları işaretleyerek noktalama, URL, mention, hashtag ve XML etiketlerini de dahil edebilirsiniz. Dar pencerelerde seçenek satırını yatay kaydırabilirsiniz.

Dışlanan birimler önce çıkarılır, ardından kalan birimler üzerinden gruplar oluşturulur. Dolayısıyla noktalama dışlandığında onun iki yanındaki birimler aynı grupta yer alabilir. Hiçbir tür seçilmezse Sözcükler kullanılır. Sonuçlar her grubun metindeki sıklığını gösterir.

### Concordance: sözcüğü bağlamıyla inceleyin

**Concordance**, aranan birimin geçtiği yerleri sol ve sağ bağlamıyla gösterir.

1. Sıklık analizi yaptıktan sonra bir satıra tıklayın veya arama alanına bir birim yazın.
2. Bağlam genişliğini **±3, ±5, ±7 veya ±10** olarak seçin. Bu sayı, aranan birimin her iki yanında gösterilecek birim sayısıdır.
3. **Concordance** düğmesine basın veya arama alanındayken Enter tuşunu kullanın.
4. **Geri** düğmesiyle önceki sıklık sonucuna dönün.

Arama büyük/küçük harften bağımsızdır ve tam birim eşleşmesi kullanır; bir sözcüğün içindeki harf parçasını aramaz.

### Metin analizi

**Metin Analizi** sekmesine geçtiğinizde analiz otomatik başlar. Ölçümleri ve grafikleri görmek için aşağı kaydırabilirsiniz.

- **Temel ölçümler:** Karakter, birim, sözlüksel birim, tekil birim ve cümle sayıları.
- **Type-token oranı:** Tekil sözlüksel birim sayısının toplam sözlüksel birim sayısına oranı; metindeki sözcük çeşitliliğine ilişkin bir ölçüm.
- **Dağılım:** Birim türlerinin sayıları.
- **POS Dağılımı:** Sözcük türlerinin sayıları.
- **Metin Profili ve Ek Bilgiler:** Uzunluk, çeşitlilik, baskın türler ve sözlüksel oran gibi özetler.

Grafikler en sık görülen ilk sekiz kategoriyi gösterir. CSV aktarımı tüm hesaplanan ölçümleri ve dağılım satırlarını içerir.

### Sonuçları filtreleme, kopyalama ve kaydetme

**Filtre**, tablodaki görünümü daraltır. **Kopyala**, satır seçiliyse seçili satırları; seçim yoksa tüm sonucu panoya kopyalar. **Temizle** menüsünden kaynak metni, sonuçları veya ikisini birden temizleyebilirsiniz.

**CSV'ye Aktar**, tüm analiz sonucunu sütun başlıklarıyla birlikte kaydeder. Filtre ve satır seçimi dışa aktarılan veriyi daraltmaz. Dosya UTF-8 kodlamalıdır ve sütunlar **tab / sekme** karakteriyle ayrılır. Excel veya başka bir programda sütunlar tek alanda görünürse dosyayı içe aktarırken ayırıcı olarak **tab / sekme** seçin.

Dosya adına tarih ve saat eklenir. Sütun başlıkları, arayüz dilinden bağımsız olarak aynı kalır.

### Ayarlar ve metin sınırı

**Ayarlar / Settings** menüsünden arayüz dilini, varsayılan birimlendirme modunu, pencere düzenini hatırlamayı, tablo yoğunluğunu ve metin sınırını değiştirebilirsiniz.

Dil değişikliği hemen uygulanır; diğer tercihler **Tamam** düğmesiyle kaydedilir. Geniş tablo yoğunluğu satırlar arasında daha fazla alan bırakır; Sıkı yoğunluk aynı alanda daha fazla kayıt gösterir. Seçili işlem sekmesi dolu renkle belirtilir.

Varsayılan maksimum birim sınırı **1.000.000** değeridir. Girişin kabul edilip edilmeyeceği metindeki normal boşlukların sayısıyla kontrol edilir; bu, analiz sonrasında elde edilen gerçek birim sayısı değildir. Karakter sınırı yoktur. Ayarlarda 1, 2 ve 5 milyon hızlı seçimlerini veya özel bir değer kullanabilirsiniz. Bir milyonun üzerindeki seçimlerde donanım kapasitesi için onay istenir; daha yüksek sınır daha fazla bellek ve işlem süresi gerektirebilir.

### Klavye kısayolları

Windows ve Linux'ta **Ctrl**, macOS'ta **⌘ Command** kullanın.

| Kısayol | İşlem |
| --- | --- |
| Ctrl / ⌘ + Enter | Birimlendir |
| Ctrl / ⌘ + Shift + P | Sözcük türü etiketle |
| Ctrl / ⌘ + Shift + F | Sıklık |
| Ctrl / ⌘ + L | Kaynak metne odaklan |
| Ctrl / ⌘ + , | Ayarları aç |
| Ctrl / ⌘ + C | Sonuç tablosunda seçimi veya tüm sonucu kopyala |

Metin alanındayken normal metin kopyalama davranışı kullanılır. Concordance arama alanındayken **Enter** aramayı başlatır.

### Yeni sürümleri kontrol etme

Uygulama açıldıktan sonra ve açık kaldığı sürece belirli aralıklarla yeni sürüm kontrolü yapar. **Sürümü Denetle** menüsünden bunu kendiniz de başlatabilirsiniz. İnternet yoksa metin analizlerini kullanmaya devam edebilirsiniz.

Sürüm kontrolü metninizi göndermez. Yeni sürüm bulunduğunda uygulama sizi bilgilendirir; güncellemeyi otomatik kurmaz. Yeni paketi indirip kurmanız gerekir.

## Yerelde kurulum ve çalıştırma

Hazır paketler yerine kaynak dosyalarından çalıştırmak isterseniz aşağıdaki adımları izleyebilirsiniz. Bu yöntem için **Python 3.11, 3.12 veya 3.13** ve ilk kurulum sırasında internet bağlantısı gerekir. Normal kullanım için yukarıdaki hazır paketler daha kolaydır.

1. [Proje sayfasında](https://github.com/tanerim/TS_TextLab) **Code → Download ZIP** seçeneğiyle kaynak dosyalarını indirin ve ZIP'i açın.
2. Oluşan klasörde terminal açın.
3. İşletim sisteminize uygun komutları sırasıyla çalıştırın.

### Windows

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -X utf8 main.py
```

### macOS ve Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -X utf8 main.py
```

Sözcük türü modeli bağımlılıklarla birlikte kurulur; ayrıca model indirmeniz gerekmez. Sonraki açılışlarda aynı klasörde yalnızca son komutu çalıştırmanız yeterlidir. Arayüz sistem diline göre Türkçe veya İngilizce açılır; Ayarlar menüsünden dili değiştirebilirsiniz.

## Bilimsel kaynak ve atıf

**Sezer, T. (2025).** *[Dizilerden birimlere: Bilişimsel dilbilim çerçevesinde bir birimlendirici tasarımı](https://tez.yok.gov.tr/UlusalTezMerkezi/TezGoster?key=Xau5rw3KuCgEuy-FuJQtsNVGSOOMCSQba2T5bZaDSDUTfOiTTVCpuBZPjDrUgB0i)* [Doktora tezi, Hacettepe Üniversitesi]. Ulusal Tez Merkezi. Tez No. 959204.

TS TextLab'ı kullandığınız bir çalışmada yazılımı ayrıca belirtmek için önerilen künye:

> Sezer, T. (t.y.). *TS TextLab* (Sürüm 0.1.1) [Bilgisayar yazılımı]. https://github.com/tanerim/TS_TextLab

Çalışmanızda kullandığınız sürüm farklıysa künyedeki sürüm numarasını değiştirin. Yöntem bölümünde örneğin “Türkçe metinlerin birimlendirilmesi ve sıklık analizi TS TextLab (sürüm 0.1.1) kullanılarak gerçekleştirilmiştir.” ifadesine yer verebilirsiniz. Yazılım künyesi öneridir; kurumunuzun veya derginizin kaynak gösterme kurallarına göre uyarlayın.

Daha fazla bilgi: [TS Corpus](https://tscorpus.com/)
