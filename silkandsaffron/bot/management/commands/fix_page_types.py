from django.core.management.base import BaseCommand
from bot.models import PageContent

class Command(BaseCommand):
    help = "Fix page_type for existing PageContent entries"

    def handle(self, *args, **options):
        self.stdout.write("🔧 Fixing page types...\n")
        
        # Get all pages
        all_pages = PageContent.objects.all()
        total = all_pages.count()
        
        updated_count = 0
        product_count = 0
        collection_count = 0
        page_count = 0
        
        for page in all_pages:
            old_type = page.page_type
            
            # Determine page type based on URL
            if '/products/' in page.url:
                page.page_type = 'product'
                product_count += 1
            elif '/collections/' in page.url:
                page.page_type = 'collection'
                collection_count += 1
            else:
                page.page_type = 'page'
                page_count += 1
            
            # Save if changed
            if old_type != page.page_type:
                page.save()
                updated_count += 1
        
        self.stdout.write("="*60)
        self.stdout.write(
            self.style.SUCCESS(f"✅ Fixed {updated_count} pages!")
        )
        self.stdout.write(f"\n📊 Final Stats:")
        self.stdout.write(f"📦 Products: {product_count}")
        self.stdout.write(f"📁 Collections: {collection_count}")
        self.stdout.write(f"📄 Other Pages: {page_count}")
        self.stdout.write(f"📊 Total: {total}")
        self.stdout.write("="*60)