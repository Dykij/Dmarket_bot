#!/bin/bash
PAYLOAD=$(cat)

# Extract tool name and target file
TOOL_NAME=$(echo "$PAYLOAD" | jq -r '.toolCall.name // empty')
TARGET_FILE=$(echo "$PAYLOAD" | jq -r '.toolCall.args.TargetFile // empty' | sed 's/^"//;s/"$//')

if [[ -z "$TARGET_FILE" || "$TARGET_FILE" == "null" ]]; then
    echo '{}'
    exit 0
fi

# Обоснование выбора: Сравниваем с git HEAD, а не с временной копией до правки.
# Почему: PostToolUse запускается ПОСЛЕ выполнения инструмента. У нас нет встроенного способа
# получить состояние файла за миллисекунду до вызова тула без стейт-трекинга в PreToolUse.
# Сравнение с HEAD означает, что если в файле уже были незакоммиченные содержательные правки,
# пустая правка сверху пройдёт (difftastic увидит старые правки относительно HEAD). Это приемлемый
# компромисс для stateless скрипта: он надёжно блокирует пустые правки на чистом файле (наиболее частый H18).
TMP_BEFORE=$(mktemp /tmp/difft_before_XXXXXX_$(basename "$TARGET_FILE"))

if ! git show "HEAD:$TARGET_FILE" > "$TMP_BEFORE" 2>/dev/null; then
    # Файла нет в HEAD (новый файл) -> считаем содержательным
    if [[ -f "$TARGET_FILE" ]]; then
        echo "WARNING: difftastic_gate.sh: git show failed but file exists on disk. Possible parsing issue with TARGET_FILE='$TARGET_FILE'" >&2
    fi
    echo '{}'
    rm -f "$TMP_BEFORE"
    exit 0
fi

difft --check-only --exit-code "$TMP_BEFORE" "$TARGET_FILE" > /dev/null 2>&1
DIFF_EXIT=$?

rm -f "$TMP_BEFORE"

if [[ $DIFF_EXIT -eq 0 ]]; then
    # 0 = No semantic/syntactic changes
    echo 'WARNING: Difftastic: Семантически пустой дифф (нет синтаксических изменений относительно HEAD). (H18 prevention).' >&2
    echo '{}'
else
    # 1 = Has changes
    echo '{}'
fi
