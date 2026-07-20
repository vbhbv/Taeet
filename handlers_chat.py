from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramAPIError
from states import ChatState
from keyboards import get_main_menu
from services.match_service import MatchmakingService
from context import correlation_id
from config import logger

router = Router()

@router.callback_query(ChatState.searching, F.data == "cancel_search")
async def cancel_search_handler(callback: CallbackQuery, state: FSMContext, match_service: MatchmakingService):
    user_id = callback.from_user.id
    cid = correlation_id.get()
    
    logger.info(f"[{cid}] User {user_id} requested search cancellation.")
    try:
        user_dto = await match_service.get_user_profile(user_id)
        if user_dto and user_dto.topic:
            await match_service.cancel_search_session(user_id, user_dto.topic, user_dto.level)
            
        await state.clear()
        await callback.message.edit_text("🛑 تم إلغاء البحث بنجاح.", reply_markup=get_main_menu())
    except Exception:
        logger.exception(f"[{cid}] Failure during cancel search for user {user_id}")
    await callback.answer()

@router.message(ChatState.in_active_chat)
async def chat_forwarding(message: Message, match_service: MatchmakingService, bot: Bot, state: FSMContext):
    user_id = message.from_user.id
    cid = correlation_id.get()
    
    user_dto = await match_service.get_user_profile(user_id)
    if not user_dto or not user_dto.is_in_chat:
        await state.clear()
        await message.answer("انتهت الجلسة أو غير موجودة.", reply_markup=get_main_menu())
        return

    # جلب الشريك من الـ Profile النظيف الممرر عبر الـ DTO لمنع تسريب الـ Pool
    async with match_service._pool.acquire() as conn:
        partner_id = await conn.fetchval("SELECT in_chat_with FROM users WHERE user_id = $1;", user_id)

    if partner_id:
        try:
            await message.copy_to(chat_id=partner_id)
        except TelegramAPIError as e:
            logger.warning(f"[{cid}] Delivery failed from {user_id} to {partner_id}: {e}")
            await match_service.terminate_debate_session(user_id)
            await state.clear()
            await message.answer("تعذر تسليم الرسالة، تم إنهاء الجلسة بسبب مغادرة الطرف الآخر.", reply_markup=get_main_menu())
