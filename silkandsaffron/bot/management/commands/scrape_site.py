# from django.core.management.base import BaseCommand
# from bot.web_scrap import scrape_all_pages

# class Command(BaseCommand):
#     help = "Scrape entire site and save into PageContent"

#     def handle(self, *args, **options):
#         domain = "https://silkandsaffron.store/"   # 👈 apna domain fix kar do
#         visited = scrape_all_pages(domain, limit=50)  # limit = max pages
#         self.stdout.write(self.style.SUCCESS(f"Scraped {len(visited)} pages from {domain}"))

from django.core.management.base import BaseCommand
from bot.web_scrap import scrape_all_pages
from bot.models import PageContent

class Command(BaseCommand):
    help = "Scrape entire Shopify store and save into PageContent"

    def add_arguments(self, parser):
        # ✅ NEW: Add optional arguments
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='Maximum number of pages to scrape (default: 100)'
        )
        
        parser.add_argument(
            '--domain',
            type=str,
            default='https://silkandsaffron.store/',
            help='Domain to scrape (default: silkandsaffron.store)'
        )
        
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before scraping'
        )

    def handle(self, *args, **options):
        domain = options['domain']
        limit = options['limit']
        clear = options['clear']
        
        # ✅ NEW: Clear existing data if requested
        if clear:
            count = PageContent.objects.count()
            PageContent.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(f"🗑️ Deleted {count} existing pages")
            )
        
        # Show stats before scraping
        existing_count = PageContent.objects.count()
        self.stdout.write(f"📊 Existing pages in database: {existing_count}\n")
        
        # Start scraping
        self.stdout.write(
            self.style.SUCCESS(f"🚀 Starting scrape of {domain}")
        )
        self.stdout.write(f"🎯 Target: {limit} pages\n")
        
        try:
            visited = scrape_all_pages(domain, limit=limit)
            
            # Show final stats
            new_count = PageContent.objects.count()
            added = new_count - existing_count
            
            self.stdout.write("\n" + "="*60)
            self.stdout.write(
                self.style.SUCCESS(f"✅ Scraping completed successfully!")
            )
            self.stdout.write(f"📊 Pages scraped: {len(visited)}")
            self.stdout.write(f"📊 New pages added: {added}")
            self.stdout.write(f"📊 Total pages in DB: {new_count}")
            
            # ✅ NEW: Show breakdown by page type
            products = PageContent.objects.filter(page_type='product').count()
            collections = PageContent.objects.filter(page_type='collection').count()
            pages = PageContent.objects.filter(page_type='page').count()
            
            self.stdout.write(f"\n📦 Products: {products}")
            self.stdout.write(f"📁 Collections: {collections}")
            self.stdout.write(f"📄 Other Pages: {pages}")
            self.stdout.write("="*60)
            
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING("\n⚠️ Scraping interrupted by user")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"\n❌ Error: {str(e)}")
            )