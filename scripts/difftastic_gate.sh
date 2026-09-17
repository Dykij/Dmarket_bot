#!/bin/bash
# Reads JSON from stdin
PAYLOAD=$(cat)

# Extract tool name and target file
TOOL_NAME=$(echo "$PAYLOAD" | jq -r '.toolCall.name // empty')
TARGET_FILE=$(echo "$PAYLOAD" | jq -r '.toolCall.args.TargetFile // empty')

if [[ -z "$TARGET_FILE" || "$TARGET_FILE" == "null" ]]; then
    echo '{"decision": "allow"}'
    exit 0
fi

# Обоснование выбора: Сравниваем с git HEAD, а не с временной копией до правки.
# Почему: PostToolUse запускается ПОСЛЕ выполнения инструмента. У нас нет встроенного способа
# получить состояние файла за миллисекунду до вызова тула без стейт-трекинга в PreToolUse.
# Сравнение с HEAD означает, что если в файле уже были незакоммиченные содержательные правки,
# пустая правка сверху пройдёт (difftastic увидит старые правки относительно HEAD). Это приемлемый
# компромисс для stateless скрипта: он надёжно блокирует пустые правки на чистом файле.
TMP_BEFORE="/tmp/difft_before_$(basename "$TARGET_FILE")"

if ! git show "HEAD:$TARGET_FILE" > "$TMP_BEFORE" 2>/dev/null; then
    # Файла нет в HEAD (новый файл) -> считаем содержательным
    echo '{"decision": "allow"}'
    exit 0
fi

difft --check-only --exit-code "$TMP_BEFORE" "$TARGET_FILE" > /dev/null 2>&1
DIFF_EXIT=$?

if [[ $DIFF_EXIT -eq 0 ]]; then
    # 0 = No semantic/syntactic changes
    echo '{"decision": "deny", "reason": "Difftastic: Семантически пустой дифф (нет синтаксических изменений относительно HEAD). Правка отклонена (H18 prevention)."}'
else
    # 1 = Has changes
    echo '{"decision": "allow"}'
fi
