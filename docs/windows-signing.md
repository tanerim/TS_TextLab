# Windows paket incelemesi ve imzalama

## Mevcut paket

12 Ekim 2026 tarihinde public v0.1.1 taşınabilir paketinin PyInstaller CArchive
indeksi okunarak doğrulanan envanter:

| Kapsam | .pyd | .dll | .exe |
| --- | ---: | ---: | ---: |
| Taşınabilir EXE'nin gömülü dosyaları | 102 | 101 | 0 |
| Taşınabilir indirmenin dış dosyası | 0 | 0 | 1 |

Kaynak: <https://github.com/tanerim/TS_TextLab/releases/download/v0.1.1/TS-TextLab-windows-x86_64.exe>.
Bu sayılar v0.1.1 taşınabilir dosyasına aittir; mevcut installer'ın kurulmuş
klasöründen ölçülmüş sayılar değildir. Spec, klasör dağıtımı ve taşınabilir EXE
için aynı `a.binaries` ve `a.datas` listesini kullanır. Klasör dağıtımında uygulama
EXE'si, kurulumdan sonra ayrıca Inno Setup'ın `unins000.exe` dosyası bulunur.
Yeni build'lerin kesin sayıları `build/windows-bundle-signing.json` ve
`build/windows-installed-signing.json` raporlarında ölçülür. Setup indirmesi ayrıca
bir dış EXE'dir; bu kapsamlar toplanırken aynı payload iki kez sayılmamalıdır.

`ujson` doğrudan requirements girdisi değildir. `ts-postagger → spaCy/Thinc →
srsly` zincirinden gelir. Yerel PyInstaller Analysis/COLLECT kayıtları ve public
Windows paketindeki `srsly\ujson\ujson.cp313-win_amd64.pyd` bunu doğrular.
`srsly`, JSON işlemleri için bu derlenmiş uzantıyı kullanır; imzalama amacıyla
paketten çıkarmak doğru çözüm değildir.
Bkz. [srsly 2.5.2 paket açıklaması](https://pypi.org/project/srsly/2.5.2/).

## Hangi dosyalar imzalanır?

`.pyd`, `.dll` ve `.exe` dosyaları Windows PE dosyalarıdır ve Authenticode ile
imzalanabilir. Script, imzasız dosyaları bizim yayıncı sertifikamızla imzalar.
Geçerli üçüncü taraf imzalarını korur; bozuk veya güvenilmeyen bir imzayı üzerine
yeni imza yazarak gizlemek yerine build'i durdurur. Envanterde dosya yolu, önceki
ve son imza durumu, yayıncı, timestamp varlığı ve SHA-256 bulunur.

İşlem sırası:

1. Windows signing yapılandırması **PyInstaller'dan önce** hazırlanır.
2. Spec, `Analysis` sonrasında bağımlılıkların özel kopyalarını oluşturur ve
   imzalar. Python ortamındaki orijinal DLL/PYD dosyaları değiştirilmez.
   Hem `COLLECT` hem taşınabilir `EXE` bu imzalı kopyaları kullanır.
   UPX ve strip kapalıdır; imzadan sonra binary değiştirilmez.
3. **Build native application ile Test packaged application and archive arasındaki**
   Windows adımı klasör dağıtımını doğrular/imzalar ve dış taşınabilir EXE'yi imzalar.
   ZIP böylece imzalı uygulamadan üretilir.
4. Inno Setup `/DWindowsSigning=1` ve `/Stextlab=...` ile derlenir.
   `SignTool=textlab`, Setup EXE'sini; `SignedUninstaller=yes`, uninstaller'ı
   derleme sırasında aynı script üzerinden imzalar.
5. Setup imzası çalıştırılmadan önce doğrulanır. Sessiz kurulumdan sonra tüm
   kurulu PE dosyaları, uninstaller dahil, doğrulanır; smoke test ve uninstall
   çalıştırılır. İmzası başarısız bir build release job'una ulaşamaz.
6. Geçici sertifika ve özel anahtar `always()` cleanup adımında kaldırılır.

Yeni imzalarda SHA-256 ve RFC 3161 timestamp zorunludur. Doğrulama
`signtool verify /pa /all` ile yapılır. Kaynaklar:
[Microsoft SignTool](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool),
[Inno Setup SignTool](https://jrsoftware.org/ishelp/topic_setup_signtool.htm),
[SignedUninstaller](https://jrsoftware.org/ishelp/topic_setup_signeduninstaller.htm).

## GitHub yapılandırması

`master` push'ları imzalama gerektirir. Sertifika/provider eksikse Windows job'u
başarısız olur ve **tüm public release engellenir**. PR'larda signing kurulumu
çalışmaz; sertifika secrets kullanılmadan imzasız test ve envanter yapılır.
Manuel workflow'da `require_windows_signing` varsayılan olarak açıktır; imzasız
deneme için kapatılabilir. Yapılandırılmış signing'deki hatalar bu seçenek kapalı
olsa bile build'i durdurur.

Hazır bir PFX ve kullanılabilir özel anahtar varsa GitHub repository Actions
secrets ekleyin:

| Secret | İçerik |
| --- | --- |
| `WINDOWS_CERTIFICATE_BASE64` | Code Signing sertifikası ve özel anahtar içeren PFX'in Base64 değeri |
| `WINDOWS_CERTIFICATE_PASSWORD` | PFX parolası |

Parolayı veya PFX içeriğini repo'ya koymayın. Windows SDK'nın x64 `signtool.exe`
dosyası runner'da otomatik bulunur. PFX yalnızca geçici runner klasöründe açılır,
`CurrentUser\My` store'a alınır ve disk kopyası hemen silinir. Özel anahtar,
geçerlilik tarihleri ve Code Signing EKU kontrol edilir.

İsteğe bağlı repository variable: `TEXTLAB_WINDOWS_TIMESTAMP_URL`
(varsayılan `http://timestamp.digicert.com`).

PFX yerine provider entegrasyonu:

- Sertifika zaten runner'ın `CurrentUser\My` store'unda ve özel anahtarı erişilebilir
  ise `TEXTLAB_WINDOWS_CERT_THUMBPRINT` variable'ını kullanın. GitHub hosted
  runner'a bu sertifikayı/provider'ı kuracak hazırlık adımı ayrıca gerekir.
- HSM/cloud sağlayıcısı için `TEXTLAB_WINDOWS_SIGN_ARGS_JSON`, SignTool'a
  eklenecek string argüman dizisidir; örneğin `['/dlib', ...]` yerine **geçerli
  JSON** olan `["/dlib", "C:\\provider\\signing.dll", "/dmdf", "C:\\provider\\metadata.json"]`.
  Sertifika/thumbprint ve bu seçenek birlikte verilmez. DLL, metadata ve provider
  kimlik doğrulamasını hazırlayan adımı Windows signing yapılandırmasından önce
  eklemek gerekir. Bu genel bağlantı noktası tek başına bir cloud hesabı kurmaz
  veya sağlayıcıya giriş yapmaz. Kimlik bilgilerini variable içine koymayın;
  sağlayıcının OIDC veya secrets yöntemini kullanın.

Repository'de sertifika veya cloud hesabı bulunmadığı için gerçek yayıncı imzası
bu yapılandırma yapılmadan üretilemez. Gerçek sertifikayla ilk Windows workflow
çalışması, SignTool/Inno Setup ve kurulu dosyaların son doğrulamasıdır.

## Raporlar ve yayın

Actions artifact'ına `build/windows-*-signing.json` raporları eklenir; CI Git
notes raporuna da alınır. `installer-test.json` içindeki `signed`, ancak imza
kontrolleri ve kurulum testleri geçtiğinde başarılı raporda `true` olur.

Mevcut v0.1.1 release otomatik değiştirilmez; release job'u var olan tag'i atlar.
İmzalı public dağıtım için `version.txt` değerini yeni sürüme yükseltip normal
release akışını çalıştırın. Sertifikayla imzalama yayıncı kimliğini doğrular;
SmartScreen itibarının veya antivirüs kararlarının her makinede aynı olmasını
garanti etmez.
