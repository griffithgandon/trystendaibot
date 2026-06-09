"""
FSM-состояния aiogram.

Заменяют telebot-овский register_next_step_handler:
каждый "следующий шаг" из старых хендлеров стал состоянием.
"""

from aiogram.fsm.state import State, StatesGroup


class UserStates(StatesGroup):
    # /start -> ввод имени (бывш. save_name)
    waiting_for_name = State()
    # Поддержка -> текст обращения (бывш. send_support)
    waiting_for_support = State()


class AdminStates(StatesGroup):
    # Ответ пользователю на обращение (бывш. send_reply);
    # id адресата кладём в state data: await state.update_data(reply_to=user_id)
    waiting_for_reply = State()
    # Рассылка всем пользователям (бывш. send_broadcast)
    waiting_for_broadcast = State()
