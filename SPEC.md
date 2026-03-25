# Telegram Бот "Запись на Ногти"

## Функционал

### Пользователь:
- Просмотр каталога стилей маникюра с фото и ценами
- Выбор нужного стиля
- Запись на свободную дату/время
- Просмотр своих записей

### Админ:
- Привязка/смена админа по username
- Добавление/удаление стилей (название, фото, цена)
- Управление расписанием (даты + слоты)
- Просмотр всех записей
- Отмена записи

## Стек
- Python 3.10+
- aiogram 3.x
- SQLite + SQLAlchemy
- python-dotenv

## База данных

### Tables:
1. **styles** — id, name, photo_url, price
2. **schedule** — id, date, time_slot, is_booked
3. **bookings** — id, user_id, username, style_id, schedule_id, created_at
4. **config** — key, value (admin_username и др.)

## Команды админа
- `/admin` — меню админки
- `/setadmin @username` — назначить админа
- `/addstyle` — добавить стиль
- `/delsyle` — удалить стиль
- `/schedule` — управление расписанием
- `/bookings` — список записей
