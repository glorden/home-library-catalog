import typer
from sqlmodel import Session, select

from app.database import engine
from app.models.user import User
from app.security import hash_password
from app.timeutil import utcnow

app = typer.Typer()


@app.command("create-admin")
def create_admin(
    email: str = typer.Option(..., help="Email единственного владельца каталога"),
) -> None:
    """Создаёт единственную строку в users. Регистрации в приложении нет."""
    with Session(engine) as session:
        if session.exec(select(User)).first() is not None:
            typer.echo("Пользователь уже существует — используйте reset-admin-password.", err=True)
            raise typer.Exit(code=1)
        password = typer.prompt("Пароль", hide_input=True, confirmation_prompt=True)
        user = User(email=email, password_hash=hash_password(password))
        session.add(user)
        session.commit()
        typer.echo(f"Создан пользователь {email}.")


@app.command("reset-admin-password")
def reset_admin_password() -> None:
    """Восстановление без email-инфраструктуры. Сбрасывает session_version,
    поэтому все ранее выданные session cookie сразу становятся недействительны."""
    with Session(engine) as session:
        user = session.exec(select(User)).first()
        if user is None:
            typer.echo("Пользователь ещё не создан — используйте create-admin.", err=True)
            raise typer.Exit(code=1)
        password = typer.prompt("Новый пароль", hide_input=True, confirmation_prompt=True)
        user.password_hash = hash_password(password)
        user.session_version += 1
        user.updated_at = utcnow()
        session.add(user)
        session.commit()
        typer.echo(f"Пароль для {user.email} обновлён, старые сессии сброшены.")


if __name__ == "__main__":
    app()
