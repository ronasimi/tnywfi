# Maintainer: Your Name <you@example.com>

pkgname=tnywfi-git
pkgver=0.1.0.r0.g0000000
pkgrel=3
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
source=("https://github.com/ronasimi/tnywfi/archive/refs/heads/master.tar.gz")
sha256sums=('2c59fd9a6d0fa021f5c8db2b1a6f904b2f77cbfddf5f5567b3d05bb26df2b84d')

package() {
  install -Dm755 "$srcdir/tnywfi-master/tnywfi.py" "$pkgdir/usr/bin/tnywfi"
  install -Dm644 "$srcdir/tnywfi-master/README.md" "$pkgdir/usr/share/doc/$pkgname/README.md"
}
