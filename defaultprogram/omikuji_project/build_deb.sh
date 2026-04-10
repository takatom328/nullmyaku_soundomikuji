#!/usr/bin/env bash
set -euo pipefail

PKG_NAME="${PKG_NAME:-star-cups-driver-rpi}"
PKG_VERSION="${PKG_VERSION:-1.0.0}"
PKG_ARCH="${PKG_ARCH:-arm64}"
MAINTAINER="${MAINTAINER:-tt18 <tt18@localhost>}"
DESCRIPTION="${DESCRIPTION:-Star CUPS driver + omikuji utility bundle for Raspberry Pi}"

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
DRIVER_SRC_DIR="${DRIVER_SRC_DIR:-/home/tt18/Downloads/Star_CUPS_Driver-3.17.0_linux/SourceCode/Star_CUPS_Driver}"
BUILD_ROOT="${PROJECT_DIR}/dist/debbuild"
STAGE_DIR="${BUILD_ROOT}/${PKG_NAME}_${PKG_VERSION}_${PKG_ARCH}"
OUTPUT_DEB="${BUILD_ROOT}/${PKG_NAME}_${PKG_VERSION}_${PKG_ARCH}.deb"

echo "==> Package: ${PKG_NAME} ${PKG_VERSION} (${PKG_ARCH})"
echo "==> Driver source: ${DRIVER_SRC_DIR}"

if [[ ! -d "${DRIVER_SRC_DIR}" ]]; then
  echo "ERROR: DRIVER_SRC_DIR not found: ${DRIVER_SRC_DIR}" >&2
  exit 1
fi

echo "==> Building Star driver binaries"
make -C "${DRIVER_SRC_DIR}" clean >/dev/null
make -C "${DRIVER_SRC_DIR}" >/dev/null

echo "==> Preparing staging tree"
rm -rf "${STAGE_DIR}"
mkdir -p "${STAGE_DIR}/DEBIAN"
mkdir -p "${STAGE_DIR}/usr/lib/cups/filter"
mkdir -p "${STAGE_DIR}/usr/share/cups/model/star"
mkdir -p "${STAGE_DIR}/opt/star-omikuji"
mkdir -p "${STAGE_DIR}/usr/bin"

echo "==> Copying CUPS filters"
cp "${DRIVER_SRC_DIR}/bin/rastertostar" "${STAGE_DIR}/usr/lib/cups/filter/"
cp "${DRIVER_SRC_DIR}/bin/rastertostarlm" "${STAGE_DIR}/usr/lib/cups/filter/"
cp "${DRIVER_SRC_DIR}/bin/rastertostarm" "${STAGE_DIR}/usr/lib/cups/filter/"
chmod 0755 "${STAGE_DIR}/usr/lib/cups/filter/rastertostar"
chmod 0755 "${STAGE_DIR}/usr/lib/cups/filter/rastertostarlm"
chmod 0755 "${STAGE_DIR}/usr/lib/cups/filter/rastertostarm"

echo "==> Copying PPD files"
cp "${DRIVER_SRC_DIR}/ppd/"*.ppd "${STAGE_DIR}/usr/share/cups/model/star/"
chmod 0644 "${STAGE_DIR}/usr/share/cups/model/star/"*.ppd

echo "==> Copying utilities"
cp "${PROJECT_DIR}/star_util.py" "${STAGE_DIR}/opt/star-omikuji/"
cp "${PROJECT_DIR}/test_print.py" "${STAGE_DIR}/opt/star-omikuji/"
cp "${PROJECT_DIR}/omikuji.py" "${STAGE_DIR}/opt/star-omikuji/"
cp "${PROJECT_DIR}/UTILITY_MANUAL.md" "${STAGE_DIR}/opt/star-omikuji/"
cp "${PROJECT_DIR}/OMIKUJI_MANUAL.md" "${STAGE_DIR}/opt/star-omikuji/"
cp "${PROJECT_DIR}/STAR_UTIL_QUICKSTART.md" "${STAGE_DIR}/opt/star-omikuji/"
chmod 0644 "${STAGE_DIR}/opt/star-omikuji/"*.md
chmod 0755 "${STAGE_DIR}/opt/star-omikuji/"*.py

echo "==> Creating launcher commands"
cat > "${STAGE_DIR}/usr/bin/star-util-rpi" <<'EOF'
#!/usr/bin/env bash
exec python3 /opt/star-omikuji/star_util.py "$@"
EOF

cat > "${STAGE_DIR}/usr/bin/omikuji-rpi" <<'EOF'
#!/usr/bin/env bash
exec python3 /opt/star-omikuji/omikuji.py "$@"
EOF

chmod 0755 "${STAGE_DIR}/usr/bin/star-util-rpi"
chmod 0755 "${STAGE_DIR}/usr/bin/omikuji-rpi"

echo "==> Writing DEBIAN metadata"
cat > "${STAGE_DIR}/DEBIAN/control" <<EOF
Package: ${PKG_NAME}
Version: ${PKG_VERSION}
Section: utils
Priority: optional
Architecture: ${PKG_ARCH}
Maintainer: ${MAINTAINER}
Depends: cups, python3, python3-pil, python3-qrcode
Description: ${DESCRIPTION}
 This package installs Star CUPS filter binaries, PPD files, and
 omikuji utility scripts for Raspberry Pi deployments.
EOF

cat > "${STAGE_DIR}/DEBIAN/postinst" <<'EOF'
#!/usr/bin/env bash
set -e
chmod 755 /usr/lib/cups/filter/rastertostar || true
chmod 755 /usr/lib/cups/filter/rastertostarlm || true
chmod 755 /usr/lib/cups/filter/rastertostarm || true
if command -v systemctl >/dev/null 2>&1; then
  systemctl restart cups || true
else
  service cups restart || true
fi
echo "star-cups-driver-rpi installed."
echo "Use 'star-util-rpi --help' and 'omikuji-rpi --help'."
EOF

cat > "${STAGE_DIR}/DEBIAN/prerm" <<'EOF'
#!/usr/bin/env bash
set -e
if command -v systemctl >/dev/null 2>&1; then
  systemctl restart cups || true
else
  service cups restart || true
fi
EOF

chmod 0755 "${STAGE_DIR}/DEBIAN/postinst"
chmod 0755 "${STAGE_DIR}/DEBIAN/prerm"
find "${STAGE_DIR}" -type d -exec chmod 0755 {} \;

echo "==> Building .deb"
mkdir -p "${BUILD_ROOT}"
if [[ "$(id -u)" -ne 0 ]] && command -v fakeroot >/dev/null 2>&1; then
  fakeroot dpkg-deb --build "${STAGE_DIR}" "${OUTPUT_DEB}" >/dev/null
else
  dpkg-deb --build "${STAGE_DIR}" "${OUTPUT_DEB}" >/dev/null
fi

echo "==> Done"
echo "Deb package: ${OUTPUT_DEB}"
echo "Install: sudo dpkg -i ${OUTPUT_DEB}"
