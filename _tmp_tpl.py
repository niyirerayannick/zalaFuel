import os
os.environ.setdefault('"'"'DJANGO_SETTINGS_MODULE'"'"','"'"'nopra_fuel.settings.development'"'"')
import django
print('"'"'env'"'"', os.environ.get('"'"'DJANGO_SETTINGS_MODULE'"'"'))
django.setup()
