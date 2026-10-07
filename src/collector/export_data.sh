#!/usr/bin/env bash
# export_data.sh: работа с веткой `data` для сборщика снимков (без состояния между запусками Actions).
#   prepare <url> <dir>              клонировать ветку data или создать пустую (orphan) локально
#   export  <raw_dir> <dir> <label>  сжать snap/ticks, скопировать run-json, закоммитить и запушить в data
set -euo pipefail

cmd="${1:?нужен prepare или export}"
GIT_USER_NAME="${GIT_USER_NAME:-github-actions[bot]}"
GIT_USER_EMAIL="${GIT_USER_EMAIL:-41898282+github-actions[bot]@users.noreply.github.com}"

case "$cmd" in
  prepare)
    url="${2:?нужен url}"
    out="${3:?нужен каталог}"
    if git ls-remote --exit-code --heads "$url" data >/dev/null 2>&1; then
      git clone --quiet --branch data --single-branch --depth 50 "$url" "$out"
      echo "ветка data найдена, клонирована в $out"
    else
      git init --quiet "$out"
      git -C "$out" remote add origin "$url"
      git -C "$out" checkout --quiet --orphan data
      printf '# Order-book snapshots from src/collector (do not edit by hand)\n' > "$out/README.md"
      git -C "$out" add README.md
      git -C "$out" -c user.name="$GIT_USER_NAME" -c user.email="$GIT_USER_EMAIL" \
        commit --quiet -m "data: init branch"
      echo "ветки data нет, создана пустая локально в $out"
    fi
    ;;
  export)
    raw="${2:?нужен каталог с raw}"
    out="${3:?нужен каталог ветки data}"
    label="${4:?нужна метка}"
    day="$(date -u +%Y/%m/%d)"
    dest="$out/snapshots/$day"
    mkdir -p "$dest"
    shopt -s nullglob
    n=0
    for f in "$raw"/snap_*.csv "$raw"/ticks_*.csv; do
      gzip -9 -c "$f" > "$dest/$(basename "$f").gz"
      n=$((n + 1))
    done
    for f in "$raw"/run_*.json; do
      cp "$f" "$dest/"
      n=$((n + 1))
    done
    if [ "$n" -eq 0 ]; then
      echo "нечего экспортировать в $raw" >&2
      exit 1
    fi
    git -C "$out" config user.name "$GIT_USER_NAME"
    git -C "$out" config user.email "$GIT_USER_EMAIL"
    git -C "$out" add -A
    if git -C "$out" diff --cached --quiet; then
      echo "изменений нет"
      exit 0
    fi
    git -C "$out" commit --quiet -m "data: $label"
    for i in 1 2 3 4 5; do
      if git -C "$out" push --quiet origin HEAD:data; then
        echo "push ok (попытка $i), файлов: $n"
        exit 0
      fi
      echo "push не прошёл (попытка $i), делаю rebase" >&2
      git -C "$out" pull --quiet --rebase origin data || true
      sleep $((2 + RANDOM % 4))
    done
    echo "push не удался за 5 попыток" >&2
    exit 1
    ;;
  *)
    echo "неизвестная команда: $cmd" >&2
    exit 2
    ;;
esac
