#!/bin/bash
PAYLOAD=$(cat)
MSG=$(echo "$PAYLOAD" | jq -r '.message.content // .content // .agentMessage // empty')

if echo "$MSG" | grep -iE '(готово|done|закрыто)' > /dev/null; then
    if ! echo "$MSG" | grep -E 'RAW:' > /dev/null; then
        cat << 'INNER_EOF'
{
  "terminationBehavior": "force_continue",
  "injectSteps": [
    {
      "type": "SYSTEM",
      "content": "ERROR: Вы попытались завершить задачу (упомянуты слова 'готово', 'done', 'закрыто'), но не приложили RAW-доказательства выполненных команд в этом же сообщении. Это нарушение правила Definition of Done. Выполните проверку и покажите вывод (RAW:), прежде чем завершать ход."
    }
  ]
}
INNER_EOF
        exit 0
    fi
fi

echo '{"terminationBehavior": "default"}'
