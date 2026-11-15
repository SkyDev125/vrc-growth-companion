#!/bin/sh
# Runs outside the frozen app; every path is supplied as a quoted environment value.
set -eu
target=$MIDSDEN_UPDATE_TARGET
package=$MIDSDEN_UPDATE_PACKAGE
result=$MIDSDEN_UPDATE_RESULT
staged="$target.update-new"
backup="$target.update-old"
mount="$(dirname "$result")/mounted"
restart() {
    if [ "$1" = darwin ]; then
        if [ "${MIDSDEN_UPDATE_SELF_TEST:-}" = 1 ]; then /usr/bin/open -n -W "$target" --args --self-test; else /usr/bin/open -n "$target"; fi
    elif [ "${MIDSDEN_UPDATE_SELF_TEST:-}" = 1 ]; then "$target" --self-test; else "$target" >/dev/null 2>&1 & fi
}
failed() {
    trap - EXIT
    printf '%s\n' 'Update failed. Your previous version was kept. See install.log.' > "$result"
    if [ -e "$backup" ]; then rm -rf "$target"; mv "$backup" "$target"; fi
    rm -rf "$staged"
    if [ "$platform" = darwin ]; then /usr/bin/hdiutil detach "$mount" >/dev/null 2>&1 || true; fi
    if [ -e "$target" ]; then restart "$platform"; fi
    exit 1
}
platform=$1
# Preflight before promising the app it can safely exit.
[ -e "$target" ] && [ -w "$(dirname "$target")" ]
[ ! -e "$staged" ] && [ ! -e "$backup" ]
printf '%s\n' ready > "$MIDSDEN_UPDATE_READY"
count=0
while kill -0 "$MIDSDEN_UPDATE_PID" 2>/dev/null; do
    count=$((count + 1)); [ "$count" -lt 120 ] || exit 1
    sleep 1
done
trap failed EXIT
if [ "$platform" = darwin ]; then
    mkdir -p "$mount"
    /usr/bin/hdiutil attach "$package" -readonly -nobrowse -mountpoint "$mount"
    /usr/bin/ditto "$mount/MidsDenCompanion.app" "$staged"
    /usr/bin/hdiutil detach "$mount"
else
    cp "$package" "$staged"
    chmod 755 "$staged"
fi
mv "$target" "$backup"
mv "$staged" "$target"
printf '%s\n' ok > "$result"
restart "$platform"
rm -rf "$backup"
trap - EXIT
