# Maintainer: Your Name <you@example.com>

pkgname=tnywfi-git
pkgver=0.1.0.r0.g0000000
pkgrel=2
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
makedepends=('curl')
source=(
  "tnywfi.py::file://$startdir/tnywfi.py"
  "README.md::file://$startdir/README.md"
)

package() {
  install -Dm755 "$srcdir/tnywfi.py" "$pkgdir/usr/bin/tnywfi"
  install -Dm644 "$srcdir/README.md" "$pkgdir/usr/share/doc/$pkgname/README.md"
}
sha256sums=('91450dacfe748b2b40a2282fae5329afba23b5cbcad9e8a961456baf0d752bf2'
            'c1a186ab307b6830c91ae8bef904f5ad7cbb3e97520989125d96a7b916b4cb98')
