from contextvars import ContextVar

current_user_id_var: ContextVar[str] = ContextVar("current_user_id", default="anonymous")


def set_current_user_id(user_id: str):
    current_user_id_var.set(user_id)


def get_current_user_id() -> str:
    return current_user_id_var.get()
