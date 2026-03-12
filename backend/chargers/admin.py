from django.contrib import admin

# Register your models here.
from .models import ChargerLocation
from .models import EVSE
from .models import Connector
from .models import Tariff
from .models import ConnectorTariff

admin.site.register(ChargerLocation)
admin.site.register(EVSE)
admin.site.register(Connector)
admin.site.register(Tariff)
admin.site.register(ConnectorTariff)
