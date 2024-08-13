import os
from datetime import datetime
import django

# Set the settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.settings")

# Set up Django
django.setup()

from mims.models import MIMSImage
from mims.services import create_alignment_estimates

# Fetch and print the test image
for test_image in MIMSImage.objects.all()[0:2]:
    print(datetime.now(), "DOING A NEW MIMS IMAGE!!!!", test_image)
    create_alignment_estimates(test_image)
