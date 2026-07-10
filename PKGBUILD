# Maintainer: Your Name <you@example.com>

pkgname=tnywfi
pkgver=0.1.0
pkgrel=1
pkgdesc="A simple GTK 3 Wi-Fi applet for NetworkManager"
arch=('any')
url="https://github.com/ronasimi/tnywfi"
license=('MIT')
depends=(
  'python'
  'python-gobject'
  'gtk3'
  'networkmanager'
  'polkit'
)
source=("$pkgname::https://github.com/ronasimi/tnywfi/archive/refs/heads/main.tar.gz")
sha256sums=('SKIP')

package() {
  cd "$srcdir/$pkgname-main"
  install -Dm755 tnywfi.py "$pkgdir/usr/bin/tnywfi"
  install -Dm644 README.md "$pkgdir/usr/share/doc/$pkgname/README.md"
}
