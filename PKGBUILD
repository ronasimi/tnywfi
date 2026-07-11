# Maintainer: Your Name <you@example.com>

pkgname=tnywfi-git
pkgver=0.1.0.r0.g0000000
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
source=(
  "tnywfi.py::https://raw.githubusercontent.com/ronasimi/tnywfi/master/tnywfi.py"
  "README.md::https://raw.githubusercontent.com/ronasimi/tnywfi/master/README.md"
)
sha256sums=('5088ec2bfe5faa57a2f6b9a06babd191196527f8d209df661dab77e18adec594'
            'c1a186ab307b6830c91ae8bef904f5ad7cbb3e97520989125d96a7b916b4cb98')

package() {
  install -Dm755 "$srcdir/tnywfi.py" "$pkgdir/usr/bin/tnywfi"
  install -Dm644 "$srcdir/README.md" "$pkgdir/usr/share/doc/$pkgname/README.md"
}
