from django.contrib import admin
from .models import PageContent

@admin.register(PageContent)
class PageContentAdmin(admin.ModelAdmin):
    # ✅ UPDATED: More useful display columns
    list_display = ("title", "page_type", "url_short", "last_scraped", "is_active")
    
    # ✅ UPDATED: Better search fields
    search_fields = ("title", "url", "content")
    
    # ✅ NEW: Filters for easier navigation
    list_filter = ("page_type", "is_active", "last_scraped")
    
    # ✅ NEW: Editable fields in list view
    list_editable = ("is_active",)
    
    # ✅ NEW: Show shortened URL
    def url_short(self, obj):
        if len(obj.url) > 50:
            return obj.url[:50] + "..."
        return obj.url
    url_short.short_description = "URL"
    
    # ✅ NEW: Actions for bulk operations
    actions = ["mark_inactive", "mark_active"]
    
    def mark_inactive(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} pages marked inactive")
    mark_inactive.short_description = "Mark selected as inactive"
    
    def mark_active(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"{queryset.count()} pages marked active")
    mark_active.short_description = "Mark selected as active"