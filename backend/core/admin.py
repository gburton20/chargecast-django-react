from django.contrib import admin

 # Register your models here.
from .models import Region
from .models import PostcodeRegionCache
from .models import ChargerLocation

admin.site.register(Region)
admin.site.register(PostcodeRegionCache)
admin.site.register(ChargerLocation)