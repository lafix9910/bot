from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
import logging

from database import get_db, get_all_bookings, confirm_booking, cancel_booking, get_or_create_master, get_masters, delete_master, get_master_by_id, get_services, delete_service, get_service_by_id, create_service, get_booking_by_id
from keyboards import get_admin_menu, get_admin_bookings_keyboard, get_admin_booking_actions, get_back_main, get_masters_management_keyboard, get_services_management_keyboard
from states import AdminAddMasterState, AdminWorkingHoursState, AdminAddServiceState
from config import ADMIN_IDS
from config import ADMIN_IDS, ADMIN_USERNAMES
import config

router = Router()
logger = logging.getLogger(__name__)


def is_admin(user_id: int, username: str = None) -> bool:
    if user_id in ADMIN_IDS:
        return True
    if username and username in ADMIN_USERNAMES:
        return True
    return False


def check_admin(callback_or_message):
    user = callback_or_message.from_user
    return is_admin(user.id, user.username)


@router.message(F.text == "/admin")
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id, message.from_user.username):
        await message.answer("⛔ Доступ запрещён")
        return
    
    await message.answer("🔧 Админ-панель:", reply_markup=get_admin_menu())


@router.callback_query(F.data == "admin_menu")
async def admin_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id, callback.from_user.username):
        await callback.answer("⛔ Доступ запрещён")
        return
    
    await callback.message.edit_text("🔧 Админ-панель:", reply_markup=get_admin_menu())
    await callback.answer()


@router.callback_query(F.data == "admin_bookings")
async def admin_bookings(callback: CallbackQuery):
    if not is_admin(callback.from_user.id, callback.from_user.username):
        await callback.answer("⛔ Доступ запрещён")
        return
    
    logger.info("Admin requesting all bookings")
    
    db = next(get_db())
    try:
        bookings = get_all_bookings(db)
        logger.info(f"Found {len(bookings)} total bookings")
        
        if not bookings:
            await callback.message.edit_text(
                "📭 Записей пока нет.",
                reply_markup=get_back_main()
            )
        else:
            await callback.message.edit_text(
                f"📋 Все записи ({len(bookings)}):",
                reply_markup=get_admin_bookings_keyboard(bookings)
            )
    except Exception as e:
        logger.error(f"Error getting all bookings: {e}")
        await callback.message.edit_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_main()
        )
    finally:
        db.close()
    
    await callback.answer()


@router.callback_query(F.data.startswith("admin_booking_"))
async def admin_booking_detail(callback: CallbackQuery):
    if not is_admin(callback.from_user.id, callback.from_user.username):
        await callback.answer("⛔ Доступ запрещён")
        return
    
    booking_id = int(callback.data.split("_")[-1])
    
    db = next(get_db())
    bookings = get_all_bookings(db)
    booking = next((b for b in bookings if b.id == booking_id), None)
    db.close()
    
    if not booking:
        await callback.answer("Запись не найдена")
        return
    
    status = "⏳ Ожидает" if booking.status == "pending" else "✅ Подтверждена" if booking.status == "confirmed" else "❌ Отменена"
    
    text = (
        f"📋 Запись #{booking.id}\n\n"
        f"👤 Клиент: @{booking.username or booking.full_name or 'Unknown'}\n"
        f"✨ Услуга: {booking.service.name}\n"
        f"💰 Цена: {booking.service.price} ₽\n"
        f"👤 Мастер: {booking.master.name}\n"
        f"📅 Дата: {booking.date.strftime('%d.%m.%Y')}\n"
        f"🕐 Время: {booking.time.strftime('%H:%M')}\n"
        f"📌 Статус: {status}"
    )
    
    await callback.message.edit_text(text, reply_markup=get_admin_booking_actions(booking_id))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_confirm_"))
async def admin_confirm(callback: CallbackQuery):
    if not is_admin(callback.from_user.id, callback.from_user.username):
        await callback.answer("⛔ Доступ запрещён")
        return
    
    booking_id = int(callback.data.split("_")[-1])
    logger.info(f"Admin confirming booking {booking_id}")
    
    db = next(get_db())
    success, user_data = confirm_booking(db, booking_id)
    
    if success and user_data:
        # Отправляем уведомление пользователю
        try:
            await callback.bot.send_message(
                user_data["user_id"],
                "✅ Ваша запись подтверждена!\n\n"
                "Мы ждём вас в назначенное время.\n"
                "До встречи!"
            )
        except Exception as e:
            logger.error(f"Failed to notify user: {e}")
    
    db.close()
    
    if success:
        await callback.message.edit_text("✅ Запись подтверждена! Клиент уведомлён.", reply_markup=get_admin_menu())
    else:
        await callback.message.edit_text("❌ Не удалось подтвердить запись", reply_markup=get_admin_menu())
    
    await callback.answer()


@router.callback_query(F.data.startswith("admin_cancel_"))
async def admin_cancel(callback: CallbackQuery):
    if not is_admin(callback.from_user.id, callback.from_user.username):
        await callback.answer("⛔ Доступ запрещён")
        return
    
    booking_id = int(callback.data.split("_")[-1])
    logger.info(f"Admin cancelling booking {booking_id}")
    
    db = next(get_db())
    success, user_data = cancel_booking(db, booking_id)
    
    if success and user_data:
        # Отправляем уведомление пользователю
        try:
            await callback.bot.send_message(
                user_data["user_id"],
                "К сожалению, ваша запись отменена.\n\n"
                "Это время занято. Свяжитесь с нами для подбора другого времени."
            )
        except Exception as e:
            logger.error(f"Failed to notify user: {e}")
    
    db.close()
    
    if success:
        await callback.message.edit_text("❌ Запись отменена! Клиент уведомлён.", reply_markup=get_admin_menu())
    else:
        await callback.message.edit_text("❌ Не удалось отменить запись", reply_markup=get_admin_menu())
    
    await callback.answer()


@router.callback_query(F.data == "admin_manage_masters")
async def admin_manage_masters(callback: CallbackQuery):
    if not is_admin(callback.from_user.id, callback.from_user.username):
        await callback.answer("⛔ Доступ запрещён")
        return
    
    db = next(get_db())
    masters = get_masters(db)
    db.close()
    
    if not masters:
        await callback.message.edit_text(
            "👥 Нет мастеров. Добавьте первого мастера:",
            reply_markup=get_masters_management_keyboard([])
        )
    else:
        await callback.message.edit_text(
            "👥 Управление мастерами:",
            reply_markup=get_masters_management_keyboard(masters)
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("admin_delete_master_"))
async def admin_delete_master(callback: CallbackQuery):
    if not is_admin(callback.from_user.id, callback.from_user.username):
        await callback.answer("⛔ Доступ запрещён")
        return
    
    master_id = int(callback.data.split("_")[-1])
    logger.info(f"Admin deleting master {master_id}")
    
    db = next(get_db())
    master = get_master_by_id(db, master_id)
    if master:
        success = delete_master(db, master_id)
        db.close()
        if success:
            await callback.message.edit_text(f"✅ Мастер '{master.name}' удалён!", reply_markup=get_admin_menu())
        else:
            await callback.message.edit_text("❌ Не удалось удалить мастера", reply_markup=get_admin_menu())
    else:
        db.close()
        await callback.message.edit_text("❌ Мастер не найден", reply_markup=get_admin_menu())
    
    await callback.answer()


@router.callback_query(F.data == "admin_add_master")
async def admin_add_master_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id, callback.from_user.username):
        await callback.answer("⛔ Доступ запрещён")
        return
    
    await callback.message.edit_text("👥 Добавление мастера\n\nВведите имя мастера:")
    await state.set_state(AdminAddMasterState.name)
    await callback.answer()


@router.message(AdminAddMasterState.name)
async def admin_add_master_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите username мастера (без @):")
    await state.set_state(AdminAddMasterState.username)


@router.message(AdminAddMasterState.username)
async def admin_add_master_username(message: Message, state: FSMContext):
    username = message.text.strip().lstrip("@")
    await state.update_data(username=username)
    await message.answer("Введите описание мастера:")
    await state.set_state(AdminAddMasterState.bio)


@router.message(AdminAddMasterState.bio)
async def admin_add_master_bio(message: Message, state: FSMContext):
    data = await state.get_data()
    logger.info(f"Adding master: {data['name']}, @{data['username']}")
    
    db = next(get_db())
    master = get_or_create_master(db, data["name"], data["username"], message.text)
    db.close()
    
    await message.answer(f"✅ Мастер '{master.name}' добавлен!", reply_markup=get_admin_menu())
    await state.clear()


@router.callback_query(F.data == "admin_hours")
async def admin_hours(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id, callback.from_user.username):
        await callback.answer("⛔ Доступ запрещён")
        return
    
    await callback.message.edit_text(
        f"⏰ Текущие рабочие часы:\n"
        f"Начало: {config.WORKING_HOURS_START}:00\n"
        f"Конец: {config.WORKING_HOURS_END}:00\n\n"
        f"Введите час начала работы (0-23):"
    )
    await state.set_state(AdminWorkingHoursState.start_hour)
    await callback.answer()


@router.message(AdminWorkingHoursState.start_hour)
async def admin_hours_start(message: Message, state: FSMContext):
    try:
        hour = int(message.text)
        if 0 <= hour <= 23:
            await state.update_data(start_hour=hour)
            await message.answer("Введите час окончания работы (0-23):")
            await state.set_state(AdminWorkingHoursState.end_hour)
        else:
            await message.answer("Введите число от 0 до 23")
    except ValueError:
        await message.answer("Введите число")


@router.message(AdminWorkingHoursState.end_hour)
async def admin_hours_end(message: Message, state: FSMContext):
    try:
        hour = int(message.text)
        if 0 <= hour <= 23:
            data = await state.get_data()
            
            await message.answer(
                f"✅ Рабочие часы обновлены:\n"
                f"Начало: {data['start_hour']}:00\n"
                f"Конец: {hour}:00\n\n"
                f"Перезапустите бота для применения изменений.",
                reply_markup=get_admin_menu()
            )
            await state.clear()
        else:
            await message.answer("Введите число от 0 до 23")
    except ValueError:
        await message.answer("Введите число")


@router.callback_query(F.data == "admin_dates")
async def admin_dates(callback: CallbackQuery):
    if not is_admin(callback.from_user.id, callback.from_user.username):
        await callback.answer("⛔ Доступ запрещён")
        return
    
    await callback.message.edit_text(
        "📅 Управление датами\n\n"
        "Даты автоматически генерируются на 14 дней вперёд.\n"
        "Свободные слоты отображаются при записи клиента.",
        reply_markup=get_admin_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_manage_services")
async def admin_manage_services(callback: CallbackQuery):
    if not is_admin(callback.from_user.id, callback.from_user.username):
        await callback.answer("⛔ Доступ запрещён")
        return
    
    db = next(get_db())
    services = get_services(db)
    db.close()
    
    if not services:
        await callback.message.edit_text(
            "✨ Нет услуг. Добавьте первую услугу:",
            reply_markup=get_services_management_keyboard([])
        )
    else:
        await callback.message.edit_text(
            "✨ Управление услугами:",
            reply_markup=get_services_management_keyboard(services)
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("admin_delete_service_"))
async def admin_delete_service(callback: CallbackQuery):
    if not is_admin(callback.from_user.id, callback.from_user.username):
        await callback.answer("⛔ Доступ запрещён")
        return
    
    service_id = int(callback.data.split("_")[-1])
    logger.info(f"Admin deleting service {service_id}")
    
    db = next(get_db())
    service = get_service_by_id(db, service_id)
    if service:
        success = delete_service(db, service_id)
        db.close()
        if success:
            await callback.message.edit_text(f"✅ Услуга '{service.name}' удалена!", reply_markup=get_admin_menu())
        else:
            await callback.message.edit_text("❌ Не удалось удалить услугу", reply_markup=get_admin_menu())
    else:
        db.close()
        await callback.message.edit_text("❌ Услуга не найдена", reply_markup=get_admin_menu())
    
    await callback.answer()


@router.callback_query(F.data == "admin_add_service")
async def admin_add_service_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id, callback.from_user.username):
        await callback.answer("⛔ Доступ запрещён")
        return
    
    await callback.message.edit_text("✨ Добавление услуги\n\nВведите название услуги:")
    await state.set_state(AdminAddServiceState.name)
    await callback.answer()


@router.message(AdminAddServiceState.name)
async def admin_add_service_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите цену услуги (число):")
    await state.set_state(AdminAddServiceState.price)


@router.message(AdminAddServiceState.price)
async def admin_add_service_price(message: Message, state: FSMContext):
    try:
        price = int(message.text)
        await state.update_data(price=price)
        await message.answer("Введите описание услуги (или /skip чтобы пропустить):")
        await state.set_state(AdminAddServiceState.description)
    except ValueError:
        await message.answer("Введите число!")


@router.message(AdminAddServiceState.description)
async def admin_add_service_desc(message: Message, state: FSMContext):
    data = await state.get_data()
    description = message.text if message.text != "/skip" else None
    
    logger.info(f"Adding service: {data['name']}, price: {data['price']}")
    
    db = next(get_db())
    service = create_service(db, data["name"], data["price"], description)
    db.close()
    
    await message.answer(f"✅ Услуга '{service.name}' за {service.price} ₽ добавлена!", reply_markup=get_admin_menu())
    await state.clear()
