import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ms_usuarios.settings')
django.setup()

from usuarios.models import Usuario

print("Creando usuarios de prueba...")

for i in range(1, 51):
    email = f"usuario{i}@bite.co"
    username = f"usuario{i}"
    password = "Test1234!"
    empresa_id = (i % 5) + 1

    if not Usuario.objects.filter(email=email).exists():
        Usuario.objects.create_user(
            email=email,
            username=username,
            password=password,
            empresa_id=empresa_id
        )
        print(f"Creado: {email}")
    else:
        print(f"Ya existe: {email}")

print(f"Seeding completo. Total usuarios: {Usuario.objects.count()}")
