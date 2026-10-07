#!/usr/bin/env bash
# GRUB2 theme installer — https://github.com/duruoxian/grub-themes
# Usage:  sudo ./install.sh            (interactive)
#         sudo ./install.sh blockterm  (direct)
set -euo pipefail

themes=(neongrid retrowave matrix nebula panda clean blockterm)
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[[ $EUID -eq 0 ]] || { echo "请用 sudo 运行：sudo ./install.sh [主题名]"; exit 1; }
command -v grub-mkconfig >/dev/null || { echo "未找到 grub-mkconfig，请先安装 grub"; exit 1; }

theme="${1:-}"
if [[ -z $theme ]]; then
  echo "可选主题："
  i=1
  for t in "${themes[@]}"; do echo "  $i) $t"; ((i++)); done
  read -rp "选择 [1-${#themes[@]}]: " n
  theme="${themes[$((n - 1))]}"
fi

[[ -d "$repo_dir/$theme" ]] || { echo "未知主题: $theme"; echo "可选: ${themes[*]}"; exit 1; }

backup="/etc/default/grub.bak-$(date +%Y%m%d-%H%M%S)"
cp /etc/default/grub "$backup"
echo "已备份原配置 -> $backup"

mkdir -p /boot/grub/themes
rm -rf "/boot/grub/themes/$theme"
cp -r "$repo_dir/$theme" /boot/grub/themes/

sed -i '/^GRUB_THEME=/d' /etc/default/grub
echo "GRUB_THEME=\"/boot/grub/themes/$theme/theme.txt\"" >> /etc/default/grub

grep -q '^GRUB_TERMINAL_OUTPUT=' /etc/default/grub || echo 'GRUB_TERMINAL_OUTPUT=gfxterm' >> /etc/default/grub
if grep -q '^GRUB_GFXMODE=' /etc/default/grub; then
  sed -i 's|^GRUB_GFXMODE=.*|GRUB_GFXMODE=2560x1440,1920x1080,auto|' /etc/default/grub
else
  echo 'GRUB_GFXMODE=2560x1440,1920x1080,auto' >> /etc/default/grub
fi

grub-mkconfig -o /boot/grub/grub.cfg

echo
echo "✅ 已启用 $theme 主题，重启生效。"
echo "   换回原配置: cp $backup /etc/default/grub && grub-mkconfig -o /boot/grub/grub.cfg"
