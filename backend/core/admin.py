from django.contrib import admin

 # Register your models here.
from .models import Region
from .models import PostcodeRegionCache

admin.site.register(Region)
admin.site.register(PostcodeRegionCache)
