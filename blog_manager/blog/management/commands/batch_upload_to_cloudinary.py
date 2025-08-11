from django.core.management.base import BaseCommand
from blog.models import PostImage
from django.core.files import File
import os


class Command(BaseCommand):
    help = "Batch upload local images to Cloudinary and update PostImage references."

    def add_arguments(self, parser):
        parser.add_argument("--dir", type=str, help="Directory containing images to upload")

    def handle(self, *args, **options):
        directory = options["dir"]
        if not directory or not os.path.isdir(directory):
            self.stderr.write(self.style.ERROR("Provide a valid directory with --dir"))
            return
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if not os.path.isfile(filepath):
                continue
            # Find PostImage with matching file name (customize as needed)
            images = PostImage.objects.filter(image=filename)
            if not images.exists():
                self.stdout.write(self.style.WARNING(f"No PostImage found for {filename}"))
                continue
            for img in images:
                with open(filepath, "rb") as f:
                    img.image.save(filename, File(f), save=True)
                self.stdout.write(self.style.SUCCESS(f"Uploaded {filename} to Cloudinary for PostImage {img.id}"))
