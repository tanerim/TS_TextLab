# TS TextLab

TS TextLab, Türkçe metinler üzerinde TS Tokenizer ve yerel spaCy tabanlı TS PosTagger modeliyle çalışan offline masaüstü uygulamasıdır.

## PyCharm Geliştirme Kurulumu

1. PyCharm'da bu klasörü proje olarak açın.
2. Python 3.10, 3.11, 3.12 veya 3.13 ile virtual environment oluşturun.
3. Bağımlılıkları kurun:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Not: Mevcut model `ts_pos_tagger/model-best` altında duruyorsa uygulama bu yolu bulur. İsterseniz modeli `models/ts_postagger_model` altına taşıyabilirsiniz.

## GUI Çalıştırma

```bash
python main.py
```

Arayüz sistem yereli Türkçe ise Türkçe, diğer durumlarda İngilizce açılır. Settings menüsünden dil tercihi kalıcı olarak değiştirilebilir. Tokenization Mode için `tokenized`, `tagged` ve `lines` çıktı modları seçilebilir.

`lines` modu çok satırlı metinlerde satır ayrımını korur. `tagged` modu tokenizer etiketlerini gösterir; bu etiketler sözcük türü etiketi değildir, verilen dizgenin işlevini tanımlar. POSTag işlemi öncesinde metin TS Tokenizer'dan geçirilir; böylece tokenizer'ın karakter düzeltme ve token sınırı çıktısı POS modeline uygulanır.

## GUI Olmadan Test

```bash
python scripts/smoke_test.py
```

## Offline Çalışma

Uygulama model indirmez ve dependency kontrolü için internete bağlanmaz. Dağıtım paketinde Python runtime, TS Tokenizer, spaCy, PySide6 ve model dosyaları birlikte paketlenmelidir.

Başlangıçta kısa timeout ile `https://tscorpus.com/tsapp/version` adresinden sürüm denetimi altyapısı çalışır. Bağlantı yoksa hata kullanıcıya gösterilmez; endpoint canlı olduğunda mevcut sürümden yeni bir değer dönerse güncelleme uyarısı gösterilir. Girilen metin bu denetime veya başka bir servise gönderilmez.

## Windows Build

Windows build işlemini Windows makinede çalıştırın:

```bash
python -m pip install -r requirements.txt
pyinstaller packaging/ts_textlab.spec --clean --noconfirm
```

Çıktı `dist/TS TextLab/TS TextLab.exe` altında oluşur.

## macOS ve Linux

Her işletim sistemi için build'i aynı işletim sisteminde üretin:

```bash
python -m pip install -r requirements.txt
pyinstaller packaging/ts_textlab.spec --clean --noconfirm
```

macOS için `.app` çıktısı DMG içine alınabilir. Linux için PyInstaller klasör çıktısı doğrudan arşivlenebilir veya AppImage aracına aktarılabilir.

## Dosya Yapısı

```text
app/
  main_window.py          # PySide6 kullanıcı arayüzü
  tokenizer_service.py    # TS Tokenizer adaptörü
  postagger_service.py    # spaCy model yükleme ve POS tagging
  resource_manager.py     # dev/build resource yolları
  logging_config.py       # log kurulumu
main.py                   # uygulama giriş noktası
scripts/smoke_test.py     # GUI'siz NLP doğrulaması
packaging/ts_textlab.spec # PyInstaller ayarları
```

## Kaynak

TS Tokenizer PyPI dokümantasyonu paket adını `ts-tokenizer`, import adını `ts_tokenizer`, Python gereksinimini 3.9+ ve çıktı modlarını `tokenized`, `tagged`, `lines`, `tagged_lines` olarak listeler: https://pypi.org/project/ts-tokenizer/
