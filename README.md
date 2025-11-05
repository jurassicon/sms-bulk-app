# SMSBulkApp

Простой веб‑сервис на Flask для массовой отправки SMS‑уведомлений. Приложение получает событие (webhook) с идентификатором пользователя из MoyKlass, запрашивает у MoyKlass телефон этого пользователя и отправляет SMS через провайдера `sms.oneclick.rs`. Логи пишутся в файл с ротацией.

## Возможности
- REST‑endpoint `POST /webhook` для запуска отправки SMS по `userId` из MoyKlass
- Получение и кэширование токена доступа MoyKlass (локальный файл, с авто‑обновлением при истечении)
- Маскирование телефонов в логах
- Ротация логов (до 10 файлов по ~1 МБ)

## Технологии
- Python 3.x
- Flask
- requests
- logging + RotatingFileHandler

Обратите внимание: в коде по умолчанию пути для логов и токена «боевые»:
- LOG_FILE_PATH: `/var/www/sms_bulk_app/sms_bulk_app.log`
- TOKEN_FILE_PATH: `/var/www/token.json`

При локальном запуске их можно переопределить или скорректировать права/каталоги.

## Переменные окружения
Укажите переменные окружения (например, через файл `.env` или в конфигурации процесса):
- `API_KEY` — API‑ключ MoyKlass
- `MOYKLASS_API_URL` — базовый URL API MoyKlass, например `https://api.moyklass.com/v1`
- `SMS_API_URL` — URL для отправки SMS у провайдера, например `https://sms.oneclick.rs/api/send`
- `SMS_USERNAME` — логин для SMS‑провайдера
- `SMS_PASSWORD` — пароль для SMS‑провайдера

Пример `.env` (не храните реальные секреты в репозитории):
```
API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
MOYKLASS_API_URL=https://api.moyklass.com/v1
SMS_API_URL=https://sms.oneclick.rs/api/send
SMS_USERNAME=smartlab_user
SMS_PASSWORD=super_secret
```

## Установка и запуск
1. Установите зависимости (создайте venv при необходимости):
   ```bash
   pip install flask requests
   ```
2. Экспортируйте переменные окружения или используйте менеджер (direnv, dotenv и т.п.).
3. Убедитесь, что каталоги для логов и токена существуют и доступны процессу:
   - `/var/www/sms_bulk_app/` для логов
   - `/var/www/` для токена `token.json`
4. Запустите приложение:
   ```bash
   python sms_bulk_app.py
   ```
   По умолчанию сервис слушает `0.0.0.0:5000`.

### Продакшн‑запуск (варианты)
- gunicorn/uwsgi + systemd или контейнеризация (Docker), с проксированием через Nginx.
- Важно: обеспечить права записи в каталог логов и к файлу токена.

## API
### POST /webhook
Запускает отправку SMS для пользователя, чей `userId` передан в теле запроса.

- Headers: `Content-Type: application/json`
- Body пример (MoyKlass‑вебхук):
  ```json
  {
    "object": {
      "userId": 123456
    }
  }
  ```

- Успешный ответ: `200 OK`
  ```json
  { "status": "success" }
  ```

- Ошибки:
  - `400 Bad Request` если не передан `userId`
  - `404 Not Found` если не найден телефон
  - `500 Internal Server Error` если ошибка при отправке SMS или недоступен провайдер

### Логика обработки
1. Принять webhook и извлечь `object.userId`.
2. Получить `accessToken` MoyKlass:
   - Если валидный токен сохранён в `/var/www/token.json`, используется он.
   - Иначе запросить новый по `POST {MOYKLASS_API_URL}/company/auth/getToken` с телом `{ "apiKey": API_KEY }`, затем сохранить токен и время истечения.
3. Запросить телефон пользователя: `GET {MOYKLASS_API_URL}/company/users/{userId}` с заголовком `x-access-token`.
4. Отправить SMS через провайдера `SMS_API_URL` с заголовками:
   - `Content-type: application/json; charset=utf-8`
   - `username: SMS_USERNAME`
   - `pwd: SMS_PASSWORD`
   и телом:
   ```json
   {
     "sender": "SmartLab",
     "message": "...текст...",
     "phone": "+3816xxxxxxx"
   }
   ```
5. Залогировать результат (телефон маскируется в логах).

## Примеры
cURL пример локального вызова:
```bash
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{"object": {"userId": 123456}}'
```

## Логи
- Формат: `'%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'`
- Путь по умолчанию: `/var/www/sms_bulk_app/sms_bulk_app.log`
- Ротация: до 10 файлов, размер ~1 МБ каждый

## Безопасность и конфиденциальность
- Не храните секреты в репозитории; используйте переменные окружения/секрет‑хранилище.
- Проверьте, кто имеет доступ к логам и файлу токена.
- Ограничьте доступ к эндпоинту (например, по IP‑фильтру или с проверкой подписи вебхука, если доступно у отправителя).

## Отладка и устранение неполадок
- Проверьте переменные окружения (выведите перед запуском или используйте `print(os.getenv(...))` временно для диагностики).
- Убедитесь, что сервер MoyKlass и SMS‑провайдер доступны из вашей сети/сервера.
- Посмотрите логи приложения (`sms_bulk_app.log`) — там будут статусы запросов и ошибки.
- Проверьте права на запись в `/var/www/` для токена и `/var/www/sms_bulk_app/` для логов.

## Лицензия
Укажите лицензию проекта (например, MIT) при необходимости.

## Контакты
Вопросы и предложения: создавайте issue или свяжитесь с ответственным за сервис.
