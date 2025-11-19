from django.db import models

class PageContent(models.Model):
    url = models.URLField(max_length=500, unique=True)
    page = models.CharField(max_length=200, blank=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    content = models.TextField()  # ✅ No limit, Django handles large text
    last_scraped = models.DateTimeField(auto_now=True)
    
    # ✅ NEW: Additional metadata
    page_type = models.CharField(max_length=50, blank=True)  # 'product', 'collection', 'page'
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-last_scraped']
        verbose_name = "Page Content"
        verbose_name_plural = "Page Contents"
    
    def __str__(self):
        return f"{self.title or self.url}"