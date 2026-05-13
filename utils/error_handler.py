def handler_errors(bot):

    def decorator(func):

        def wrapper(call):

            try:
                return func(call)

            except Exception as e:
                print(f"HANDLER ERROR [{func.__name__}]:", e)

                try:
                    bot.answer_callback_query(
                        call.id,
                        "❌ Ошибка"
                    )
                except:
                    pass

        return wrapper

    return decorator