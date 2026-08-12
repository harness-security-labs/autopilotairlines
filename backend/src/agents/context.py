from contextvars import ContextVar

current_user_id_var: ContextVar[str] = ContextVar("current_user_id", default="anonymous")
current_user_role_var: ContextVar[str] = ContextVar("current_user_role", default="anonymous")
current_user_email_var: ContextVar[str] = ContextVar("current_user_email", default="")


def set_current_user_context(user_id: str, role: str, email: str = "") -> None:
    current_user_id_var.set(user_id)
    current_user_role_var.set(role)
    current_user_email_var.set(email)


def get_current_user_id() -> str:
    return current_user_id_var.get()


def get_current_user_role() -> str:
    return current_user_role_var.get()


def get_current_user_email() -> str:
    return current_user_email_var.get()
