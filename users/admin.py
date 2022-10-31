from django.contrib import admin
from .models import OdiUser, Company, Assessor, Assessee


admin.site.register(OdiUser)
admin.site.register(Company)
admin.site.register(Assessor)
admin.site.register(Assessee)
