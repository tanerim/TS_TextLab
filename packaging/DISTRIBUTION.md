# Son kullanıcıya dağıtım

Windows, macOS ve Linux paketleri GitHub Actions'ın kendi işletim sistemi
runner'larında derlenir. Üç platformun testleri başarılı olduğunda master
branch'teki `version.txt` sürümü için GitHub Releases yayını oluşturulur.
Son kullanıcılar Releases dosyalarını doğrudan indirir; GitHub hesabı veya
Python kurulumu gerekmez. Actions artifact ZIP dosyaları geliştirici içindir.
Yayınlanmış bir sürüm otomatik olarak değiştirilmez.

Release dosyaları sabit adlarla yayımlanır: Windows kurulum ve taşınabilir
EXE'leri, Apple Silicon DMG'si, Linux x86_64 TAR.GZ arşivi ve
`SHA256SUMS.txt`. İmzasız DMG'nin dosya adında `-unsigned` bulunur.

## Linux

`TS-TextLab-linux-x86_64.tar.gz` arşivini açıp içindeki **TS TextLab**
uygulamasını çalıştırın. `_internal` klasörü yanında kalmalıdır. Aynı
klasördeki `install-linux.sh` uygulama menüsüne kullanıcıya ait bir
kısayol ekler. CI hem derleme klasöründeki uygulamayı hem de arşivden
çıkarılmış uygulamayı ve kısayol kurulumunu sınar.

Paket Ubuntu 24.04 üzerinde üretilir; daha eski glibc sürümleriyle veya
tüm Linux dağıtımlarıyla uyumluluk garanti edilmez.

## Windows

`TS-TextLab-<sürüm>-windows-x86_64.exe` tek dosyalı, kurulumsuz uygulamadır.
İndirip çift tıklamak yeterlidir. Python veya ayrıca bir klasör gerekmez.
Modelin geçici klasöre çıkarılması nedeniyle açılış daha uzun sürebilir.
CI bu dosyayı klasör dağıtımından bağımsız olarak çalıştırıp test eder.

`TS-TextLab-<sürüm>-windows-x86_64-Setup.exe` dosyasını dağıtın.
Çift tıklama kurulum sihirbazını açar, uygulama kullanıcı hesabına kurulur.
Masaüstü ve Başlat menüsü kısayolları eklenir. Python kurulumu gerekmez.
CI, sessiz kurulumdan sonra kurulan uygulamanın tüm kontrollerini çalıştırır,
Başlat menüsü kısayolunu kontrol eder ve kaldırmayı doğrular.

Mevcut Windows kurulum dosyası Authenticode imzası taşımaz. İnternetten
indirilen imzasız bir dosya Windows SmartScreen uyarısı gösterebilir;
uyarı olmadan çalışacağı garanti edilmez. Sertifika mevcut olduğunda
uygulama ve kurulum dosyası dağıtımdan önce imzalanmalıdır.

## macOS

`TS-TextLab-<sürüm>-macos-arm64.dmg` imzalı dağıtım dosyasıdır.
Sertifika ve notarization yapılandırılmamışsa onaylanan imzasız dağıtım
`-unsigned.dmg` adıyla yayımlanır; macOS ilk açılışı engelleyebilir.
CI, disk imajını salt okunur bağlar ve içindeki uygulamayı
çalıştırarak tüm işlevleri sınar. Bu test Gatekeeper onayının yerine geçmez.

Apple Developer Program hesabından Developer ID Application sertifikası
alınmalıdır. Sertifika ve parolalar kaynak koduna veya sohbet mesajına
yazılmamalıdır. GitHub repository Settings > Secrets and variables > Actions
alanında aşağıdaki secrets tanımlanır:

- `MACOS_CERTIFICATE_BASE64`: özel anahtarını içeren `.p12` sertifikasının base64 içeriği.
- `MACOS_CERTIFICATE_PASSWORD`: `.p12` parolası.
- `APPLE_ID`: Developer hesabı.
- `APPLE_TEAM_ID`: takım kimliği.
- `APPLE_APP_PASSWORD`: notarization için uygulamaya özel Apple parolası.

Repository variable olarak `TEXTLAB_MACOS_SIGN_IDENTITY`, sertifikadaki
`Developer ID Application: ... (...)` kimliğine ayarlanır.

Workflow'u `require_macos_signing=true` ile çalıştırmak imzasız dağıtımı reddeder.
Sertifika mevcutsa PyInstaller uygulamayı hardened runtime ile imzalar.
Paketleme betiği uygulamayı ve DMG'yi Apple'a gönderir, onay biletlerini ekler,
`codesign`, `spctl` ve `stapler` doğrulamalarını yapar.

Yerel macOS derlemesinde sertifikayı Keychain'e ekleyin, notarytool credential
profile oluşturun, `TEXTLAB_MACOS_SIGN_IDENTITY` ve `TEXTLAB_NOTARY_PROFILE`
değişkenlerini ayarlayın. Ardından PyInstaller ve
`scripts/create_desktop_installer.py --require-signing` çalıştırılır.

## Yayın öncesi kontrol

İmzalı DMG'yi derleme makinesi dışında bir Mac'te tarayıcıyla indirip
Gatekeeper açıkken çalıştırın. Windows kurulum dosyasını da temiz bir
kullanıcı hesabında tarayıcıyla indirip kurun. CI'nin süreç içinden başlatma
testleri, tarayıcı indirmesinin getirdiği güvenlik işaretlerini sınamaz.

Apple referansı: https://developer.apple.com/developer-id/
