"""Crea o actualiza un usuario de la app. Correr manualmente en la
terminal (no hay pantalla de "registro" dentro de la app, ya que solo
son 3 usuarios conocidos):

    python crear_usuario.py
"""
import getpass

import auth
import db


def main() -> None:
    print("=== Crear / actualizar usuario ===")
    username = input("Usuario (sin espacios, ej. 'andres'): ").strip().lower()
    if not username:
        print("El usuario no puede estar vacío.")
        return

    existente = db.obtener_usuario(username)

    if existente:
        print(f"El usuario '{username}' ya existe ({existente['nombre_completo']}).")
        password = getpass.getpass("Nueva contraseña: ")
        confirmacion = getpass.getpass("Confirma la nueva contraseña: ")
        if password != confirmacion:
            print("Las contraseñas no coinciden. No se hizo ningún cambio.")
            return
        hash_pw, salt = auth.hashear_password_nueva(password)
        db.actualizar_password_usuario(username, hash_pw, salt)
        print(f"Contraseña actualizada para '{username}'.")
    else:
        nombre_completo = input("Nombre completo: ").strip()
        password = getpass.getpass("Contraseña: ")
        confirmacion = getpass.getpass("Confirma la contraseña: ")
        if password != confirmacion:
            print("Las contraseñas no coinciden. No se creó el usuario.")
            return
        hash_pw, salt = auth.hashear_password_nueva(password)
        db.crear_usuario(username, nombre_completo, hash_pw, salt)
        print(f"Usuario '{username}' creado correctamente.")


if __name__ == "__main__":
    main()
