from datetime import timedelta
from django.contrib.auth.models import User
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.forms import ValidationError
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils.http import urlencode
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
import os
from email.mime.image import MIMEImage
import uuid
from PIL import Image
from django.conf import settings
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError
from .utils.msds_validation import validate_file_size
import shortuuid
from django.core.exceptions import ObjectDoesNotExist
import logging


security_logger = logging.getLogger('django.security')

static_img_path = os.path.join(settings.BASE_DIR, 'static')


def generate_short_uuid():
    """Generate a short UUID for model primary keys"""
    return shortuuid.uuid()


def msds_upload_path(instance, filename):
    """Generate unique path for MSDS files"""
    ext = filename.split('.')[-1]
    unique_filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('msds_files', unique_filename) # Change 'msds_files' to private one with auth


class UserApplication(models.Model):
    """Model for user registrations"""
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    workplace = models.CharField(max_length=100)
    department = models.CharField(max_length=100)
    id_image = models.ImageField(
            upload_to='user_applications/',
            help_text="Upload a clear photo of your work ID"
    )
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'User Application'
        verbose_name_plural = 'User Applications'

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def save(self, *args, **kwargs):
        # Delete old image if updating
        if self.pk:
            try:
                old_instance = UserApplication.objects.get(pk=self.pk)
                if old_instance.id_image and old_instance.id_image != self.id_image:
                    old_instance.id_image.delete(save=False)
            except ObjectDoesNotExist:
                pass

        super().save(*args, **kwargs)

        # Process image only if it's a new image or being updated
        try:
            # Resize and optimize image after saving
            img_path = self.id_image.path
            img = Image.open(img_path)

            # Convert to RGB if RGBA
            if img.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1])
                img = background

            # Resize maintaning aspect ratio
            max_size = (800, 800)
            img.thumbnail(max_size, Image.LANCZOS)

            # Save with optimized quality
            img.save(img_path, quality=70, optimize=True)
        except Exception as e:
            security_logger.error(
                    "Image processing failed",
                    extra={
                        'error': str(e),
                        'stack': traceback.format_exc()
                    }
            )
            print(f"Image processing failed: {e}")


@receiver(post_save, sender=UserApplication)
def send_approval_email(sender, instance, created, **kwargs):
    """Send approval email when application is approved"""
    if instance.is_approved and not getattr(instance, '_approval_email_sent', False):
        subject = 'Application Approved'
        recipient_list = [instance.email]

        # Generate prefilled form link
        token = uuid.uuid4().hex
        url = reverse('register_project_manager')
        params = urlencode({
            'email': instance.email,
            'first_name': instance.first_name,
            'last_name': instance.last_name,
            'token': token
        })

        # Render the HTML template as a string
        html_message = render_to_string(
                'inventory/approved_mail_template.html',
                {'url': url, 'params': params}
        )
        msg = EmailMultiAlternatives(
                subject,
                html_message,
                settings.EMAIL_HOST_USER,
                recipient_list
        )

        msg.mixed_subtype = 'related'
        msg.attach_alternative(html_message, "text/html")

        email_images = ["check.png", "Logo_Orange.png", "Logo_White.png",
                        "facebook2x.png", "instagram2x.png",
                        "linkedin2x.png", "twitter2x.png"]

        for root, _, files in os.walk(f"{static_img_path}/images/"):
            for file in files:
                if file in email_images:
                    file_path = os.path.join(root, file)
                    filename = os.path.splitext(file)[0]
                    try:
                        with open(file_path, 'rb') as img_file:
                            img = MIMEImage(img_file.read())
                            img.add_header('Content-Id', f'<{filename}>')
                            msg.attach(img)
                    except Exception as e:
                        print(f"Failed to attached image {file}: {e}")
        try:
            msg.send()
            instance._approval_email_sent = True
        except Exception as e:
            print("Email failed to send:", e)


class Project(models.Model):
    """Models representing research project"""
    name = models.CharField(max_length=255, unique=True)
    project_manager = models.ForeignKey(
            User,
            on_delete=models.CASCADE,
            related_name='managed_projects',
            null=True,
            blank=True
    )
    project_editors = models.ManyToManyField(
            User,
            related_name='edited_projects',
            blank=True
    )
    project_members = models.ManyToManyField(
            User,
            related_name='member_projects',
            blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Project'
        verbose_name_plural = 'Projects'

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    """Extended user profile information"""
    user = models.OneToOneField(
            User,
            on_delete=models.CASCADE,
            related_name='profile'
    )
    managed_projects = models.ManyToManyField(
            Project,
            related_name='managing_users',
            blank=True
    )
    department = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f"Profile for {self.user.username}"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a profile when a new user is created"""
    if created:
        UserProfile.objects.create(user=instance)


#@receiver(post_save, sender=User)
#def save_user_profile(sender, instance, **kwargs):
#    """Save the profile when the user is saved"""
#    try:
#        instance.profile.save()
#    except ObjectDoesNotExist:
#        UserProfile.objects.create(user=instance)


class Log(models.Model):
    """Audit log for tracking user actions"""
    id = models.CharField(
            primary_key=True,
            max_length=22,
            unique=True,
            default=generate_short_uuid,
            editable=False
    )
    project = models.ForeignKey(
            Project,
            on_delete=models.CASCADE,
            related_name='logs'
    )
    user = models.ForeignKey(
            User,
            on_delete=models.CASCADE,
            related_name='action_logs'
    )
    action = models.CharField(max_length=255)
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Log Entry'
        verbose_name_plural = 'Log Entries'

    def __str__(self):
        return f"{self.action} by {self.user.username} on {self.project.name}"


class BaseInventoryItem(models.Model):
    """Abstract base model for inventory items"""
    TEMPERATURE_UNITS = [
            ('C', 'C'),
            ('F', 'F')
    ]

    id = models.CharField(
        primary_key=True,
        max_length=22,
        unique=True,
        default=generate_short_uuid,
        editable=False
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='%(class)s_items'
    )
    name = models.CharField(max_length=100)
    product_code = models.CharField(max_length=100, blank=True)
    items_per_pack = models.PositiveIntegerField()
    items_left_in_pack = models.PositiveIntegerField()
    pack_count = models.PositiveIntegerField(default=1)
    expiry_date = models.DateField(null=True, blank=True)
    date_recorded = models.DateField(auto_now_add=True)
    storage_location = models.CharField(max_length=100, blank=True)
    cold_storage = models.CharField(max_length=50)
    oem_temperature = models.IntegerField(
            null=True,
            blank=True,
            help_text="Manufacturer recommended storage temperature."
    )
    temperature_unit = models.CharField(
            max_length=1,
            choices=TEMPERATURE_UNITS,
            default='C'
    )
    vendor = models.CharField(max_length=100, blank=True)
    threshold_value = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.name} ({self.product_code})" if self.product_code else self.name

    def clean(self):
        """Validate inventory item data"""
        super().clean()

        if self.items_left_in_pack > self.items_per_pack:
            raise ValidationError(
                "Current quantity cannot exceed pack size"
            )

        if self.expiry_date and self.expiry_date < timezone.now().date():
            raise ValidationError(
                "Expiry date cannot be in the past"
            )

        if self.oem_temperature is not None:
            if self.temperature_unit == 'C' and self.oem_temperature < -273:
                raise ValidationError(
                        "Temperature cannot be below absolute zero (-273°C)"
                )
            elif self.temperature_unit == 'F' and self.oem_temperature < -459:
                raise ValidationError(
                        "Temperature cannot be below absolute zero (-459°F)"
                )

            # Reasonable upper limits
            if self.temperature_unit == 'C' and self.oem_temperature > 100:
                raise ValidationError("Temperature seems unusually high for storage")
            elif self.temperature_unit == 'F' and self.oem_temperature > 200:
                raise ValidationError("Temperature seems unusually high for storage")

    @property
    def percentage_remaining(self):
        """Calculate percentage of items remaining"""
        if self.items_per_pack == 0:
            return 0
        return round((self.items_left_in_pack / self.items_per_pack) * 100, 2)

    @property
    def is_below_threshold(self):
        """Check if item is below threshold"""
        if self.threshold_value is None:
            return False
        return self.items_left_in_pack < self.threshold_value

    @property
    def temperature_display(self):
        if not self.oem_temperature:
            return "N/A"
        return f"{self.oem_temperature}°{self.temperature_unit}"

    def can_access(self, user):
        """Check if user can access this consumable"""
        return (user == self.project.project_manager or
                user in self.project.project_editors.all() or
                user in self.project.project_members.all())

    def is_just_member(self, user):
        """Check if user is just member"""
        return user in self.project.project_members.all()

    def _get_expiry_status(self):
        """Calculate all expiry statuses at once (efficient)"""
        if not hasattr(self, '_expiry_cache'):
            today = timezone.now().date()
            self._expiry_cache = {
                'today': today,
                'is_expired': self.expiry_date and self.expiry_date < today,
                'days_until': (self.expiry_date - today).days if self.expiry_date else None,
                'in_7_days': self.expiry_date and today <= self.expiry_date <= (today + timedelta(days=7)),
                'in_30_days': self.expiry_date and today <= self.expiry_date <= (today + timedelta(days=30)),
            }
        return self._expiry_cache

    @property
    def is_expiring_in_30_days(self):
        return self._get_expiry_status()['in_30_days']

    @property
    def is_expiring_in_7_days(self):
        return self._get_expiry_status()['in_7_days']

    @property
    def is_expired(self):
        return self._get_expiry_status()['is_expired']

    @property
    def days_until_expiry(self):
        return self._get_expiry_status()['days_until']

    @property
    def is_reagent_low_stock(self):
        return self.pack_count < self.threshold_value


class BaseInventoryManager(models.Manager):
    """Custom manager for Reagent model with project-specific methods"""

    def for_project(self, project_name):
        """Filter reagents for a specific project"""
        return self.filter(project__name=project_name)

    def get_project_stats(self, project_name):
        """Get statistics for a specific project"""
        queryset = self.for_project(project_name)

        return {
            'total_count': queryset.count(),
            'low_stock_count': queryset.filter(
                threshold_value__isnull=False,
                pack_count__lt=models.F('threshold_value')
            ).count(),
            'expired_count': queryset.filter(
                expiry_date__lt=timezone.now().date()
            ).count(),
            'expiring_soon_count': queryset.filter(
                expiry_date__range=[
                    timezone.now().date(),
                    timezone.now().date() + timedelta(days=30)
                ]
            ).count(),
            'expiring_in_a_week': queryset.filter(
                expiry_date__range=[
                    timezone.now().date(),
                    timezone.now().date() + timedelta(days=7)
                ]
            ).count(),  # If you want the items, remove count() and slice a list with limit
        }


class Consumable(BaseInventoryItem):
    """Model for laboratory consumables"""
    objects = BaseInventoryManager()

    class Meta:
        ordering = ['name']
        verbose_name = 'Consumable'
        verbose_name_plural = 'Consumables'


class Reagent(BaseInventoryItem):
    """Model for laboratory reagents"""
    country_of_origin = models.CharField(max_length=100, null=True)
    hazard_level = models.PositiveSmallIntegerField(
            null=True,
            blank=True,
            validators=[MaxValueValidator(4)],
            help_text="Hazard level from 0 (none) to 4 (severe)"
    )

    objects = BaseInventoryManager()

    class Meta:
        ordering = ['name']
        verbose_name = 'Reagent'
        verbose_name_plural = 'Reagents'

    def clean(self):
        """Additional validation"""
        super().clean()

        # Hazard level validation
        if self.hazard_level is not None:
            if self.hazard_level < 0 or self.hazard_level > 4:
                raise ValidationError("Hazard level must be between 0 and 4")

            # Additional validation based on hazard level
            if self.hazard_level >= 3 and not self.msds_files.exists():
                raise ValidationError("MSDS required for hazard level 3 and above")


class MSDSFile(models.Model):
    """Model for Material Safety Data Sheet files"""
    # File storage fields
    file = models.FileField(
            upload_to=msds_upload_path,
            validators=[validate_file_size]
    )
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(help_text="Files size bytes") # in bytes
    file_hash = models.CharField(max_length=64) # SHA-256 hash

    # Metadata
    reagent = models.ForeignKey(
            Reagent,
            on_delete=models.CASCADE,
            related_name='msds_files'
    )
    uploaded_by = models.ForeignKey(
            User,
            on_delete=models.SET_NULL,
            null=True,
            related_name='uploaded_msds_files'
    )
    upload_date = models.DateTimeField(auto_now_add=True)
    last_verified = models.DateTimeField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    verification_notes = models.TextField(blank=True)

    # Virus scan results
    scan_result = models.CharField(
            max_length=20,
            default='pending',
            choices=[
                ('pending', 'Pending'),
                ('clean', 'Clean'),
                ('infected', 'Infected'),
                ('error', 'Error')
            ]
    )

    class Meta:
        permissions = [
                ('upload_msds', 'Can upload MSDS Files'),
                ('view_msds', 'Can view MSDS files'),
                ('verify_msds', 'Can verify MSDS content'),
        ]
        ordering = ['-upload_date']
        verbose_name = 'MSDS File'
        verbose_name_plural = 'MSDS Files'

    def __str__(self):
        return f"MSDS for {self.reagent.name} ({self.original_filename})"

    def save(self, *args, **kwargs):
        if not self.pk:
            self.original_filename = self.file.name.split('/')[-1]
            self.file_size = self.file.size
            self.file_hash = self.calculate_file_hash()
        super().save(*args, **kwargs)

    def calculate_file_hash(self):
        """Calculate SHA-256 hash of the file"""
        import hashlib
        hash_sha256 = hashlib.sha256()
        self.file.seek(0)
        for chunk in self.file.chunks():
            hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def clean(self):
        """Validate the file before saving"""
        super().clean()

        # Check file size (5MB limit)
        if self.file.size > 5 * 1024 * 1024:
            raise ValidationError("File size exceeds 5MB limit")

        # Verify PDF validity
        try:
            self.file.seek(0)   # Reset file pointer
            reader = PdfReader(self.file)

            if len(reader.pages) == 0:
                raise ValidationError("The PDF file appears to be empty or corrupted")

            # Basic content check
            total_text = ""
            for page in reader.pages[:3]:   # Check first 3 pages
                total_text += page.extract_text() or ""

            if len(total_text.strip()) < 50:    # At least 50 characters of text
                raise ValidationError("The PDF appears to contain very little text content. PLease verify it's a valid MSDS.")

        except PdfReadError as e:
            raise ValidationError(f"Invalid PDF file: {str(e)}")
        except Exception as e:
            raise ValidationError(f"Error reading PDF file: {str(e)}")
        finally:
            self.file.seek(0)  # Reset file pointer after validation

    def get_absolute_url(self):
        """Get secure download URL with access control"""
        from django.urls import reverse
        return reverse('download_msds', kwargs={'msds_id': self.id})

    def can_access(self, user):
        """Check if user can access this MSDS file"""
        return (user == self.reagent.project.project_manager or
                user in self.reagent.project.project_editors.all() or
                user in self.reagent.project.project_members.all())


class MSDSSection(models.Model):
    """Configurable sections expected in MSDS files"""
    name = models.CharField(max_length=100)
    required = models.BooleanField(default=True)
    keywords = models.TextField(
            help_text="Comma-separated keywords to identify this section"
    )
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        verbose_name = 'MSDS Section'
        verbose_name_plural = 'MSDS Sections'

    def __str__(self):
        return self.name


class MSDSValidationResult(models.Model):
    """Results of content validation"""
    msds_file = models.ForeignKey(
            MSDSFile,
            on_delete=models.CASCADE,
            related_name='validation_results'
    )
    section = models.ForeignKey(
            MSDSSection,
            on_delete=models.CASCADE,
            related_name='validation_results'
    )
    found = models.BooleanField(default=False)
    match_quality = models.FloatField(
            null=True,
            blank=True,
            validators=[MinValueValidator(0), MaxValueValidator(1)]
    )
    extracted_text = models.TextField(blank=True)
    validation_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'MSDS Validation Result'
        verbose_name_plural = 'MSDS Validation Results'
        unique_together = ('msds_file', 'section')

    def __str__(self):
        return f"{self.section.name} - {'Found' if self.found else 'Missing'}"


class Equipment(models.Model):
    """Model for laboratory equipment"""
    STATUS_CHOICES = [
        ('operational', 'Operational'),
        ('maintenance', 'Under Maintenance'),
        ('faulty', 'Faulty'),
        ('retired', 'Retired'),
    ]

    project = models.ForeignKey(
            Project,
            on_delete=models.CASCADE,
            related_name='equipment'
    )
    name = models.CharField(max_length=100)
    equip_id = models.CharField(
            max_length=100,
            unique=True,
            help_text="Unique equipment identifier"
    )
    serial_num = models.CharField(
            max_length=100,
            null=True,
            unique=True,
            blank=True
    )
    status = models.CharField(
            max_length=20,
            choices=STATUS_CHOICES,
            default='operational'
    )
    service_contract_start = models.DateField(null=True, blank=True)
    service_contract_end = models.DateField(null=True, blank=True)
    date_installed = models.DateField(default=timezone.now)
    source = models.CharField(max_length=100, blank=True)
    operating_temperature = models.IntegerField(null=True, blank=True)
    storage_location = models.CharField(max_length=100, null=True)
    warranty_end_date = models.DateField(null=True, blank=True)
    last_calibration_date = models.DateField(null=True, blank=True)
    next_calibration_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Equipment'
        verbose_name_plural = 'Equipment'

    def __str__(self):
        return f"{self.name} ({self.equip_id})"

    def clean(self):
        """Validate equipment data"""
        super().clean()

        if (self.service_contract_start and self.service_contract_end and
                self.service_contract_start > self.service_contract_end):
            raise ValidationError(
                "Service contract start date cannot be after end date"
            )

        if (self.last_calibration_date and self.next_calibration_date and
                self.last_calibration_date > self.next_calibration_date):
            raise ValidationError(
                "Last calibration date cannot be after next calibration date"
            )


class Rooms(models.Model):
    """Model for room where storages are kept"""
    id = models.CharField(
            primary_key=True,
            max_length=22,
            unique=True,
            default=generate_short_uuid,
            editable=False
    )
    room_name = models.CharField(max_length=200)
    building = models.CharField(max_length=100)
    notes = models.TextField(blank=True, null=True)


class Storages(models.Model):
    """Models for storages where shelves, racks and boxes are kept"""
    TEMPERATURE_UNITS = [
            ('C', 'C'),
            ('F', 'F')
    ]
    id = models.CharField(
            primary_key=True,
            max_length=22,
            unique=True,
            default=generate_short_uuid,
            editable=False
    )
    room_id = models.ForeignKey(
            Rooms,
            on_delete=models.CASCADE,
            related_name='storages'
    )
    storage_name = models.CharField(max_length=70)
    storage_type = models.CharField(max_length=70)
    temperature = models.IntegerField()
    temperature_unit = models.CharField(
            max_length=1,
            choices=TEMPERATURE_UNITS,
            default='C'
    )
    notes = models.TextField(blank=True, null=True)

    def clean(self):
        """Validate inventory item data"""
        super().clean()

        if self.temperature is not None:
            if self.temperature_unit == 'C' and self.temperature < -273:
                raise ValidationError(
                        "Temperature cannot be below absolute zero (-273°C)"
                )
            elif self.temperature_unit == 'F' and self.temperature < -459:
                raise ValidationError(
                        "Temperature cannot be below absolute zero (-459°F)"
                )

            # Reasonable upper limits
            if self.temperature_unit == 'C' and self.temperature > 100:
                raise ValidationError("Temperature seems unusually high for storage")
            elif self.temperature_unit == 'F' and self.temperature > 200:
                raise ValidationError("Temperature seems unusually high for storage")

    @property
    def temperature_display(self):
        if not self.temperature:
            return "N/A"
        return f"{self.temperature}°{self.temperature_unit}"


class StorageLocation(models.Model):
    """Abstract base model for storage locations"""
    name = models.CharField(max_length=100)
    notes = models.TextField(blank=True)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='%(class)s_locations'
    )
    project_manager = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='%(class)s_locations',
        null=True,
        blank=True,
        help_text="The project manager who owns this storage location"
    )
    location_code = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        unique=True,
        help_text="Unique identifier for this location"
    )
    temperature = models.IntegerField(null=True, blank=True)
    capacity = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Total capacity in items or units"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.location_code})"

    def save(self, *args, **kwargs):
        if not self.project_manager and self.project:
            self.project_manager = self.project.project_manager
        super().save(*args, **kwargs)


class Shelf(models.Model):
    """Model for shelf storage locations"""
    id = models.CharField(
            primary_key=True,
            max_length=22,
            unique=True,
            default=generate_short_uuid,
            editable=False
    )
    storage = models.ForeignKey(
            Storages,
            on_delete=models.CASCADE,
            related_name='shelves'
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='project_shelves'
    )
    project_manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='project_manager_shelves',
        help_text="The project manager who owns this Shelf"
    )
    shelf_label = models.CharField(
            max_length=50,
            help_text="e.g.,Shelf 1, Top Shelf"
    )
    capacity = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Total capacity in items or units"
    )
    notes = models.TextField()

    def save(self, *args, **kwargs):
        if not self.project_manager and self.project:
            self.project_manager = self.project.project_manager
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Shelf'
        verbose_name_plural = 'Shelves'


class Rack(models.Model):
    """Model for rack storage locations"""
    id = models.CharField(
            primary_key=True,
            max_length=22,
            unique=True,
            default=generate_short_uuid,
            editable=False
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='shelf_racks'
    )
    project_manager = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='project_manager_racks',
        help_text="The project manager who owns this Rack"
    )
    shelf = models.ForeignKey(
            Shelf,
            on_delete=models.CASCADE,
            related_name='racks'
    )
    rack_label = models.CharField(max_length=50)
    capacity = models.PositiveIntegerField(
            help_text="Total capacity in boxes"
    )
    notes = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.project_manager and self.project:
            self.project_manager = self.project.project_manager
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Rack'
        verbose_name_plural = 'Racks'


class Box(models.Model):
    """Model for box storage locations"""
    id = models.CharField(
            primary_key=True,
            max_length=22,
            unique=True,
            default=generate_short_uuid,
            editable=False
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='rack_boxes'
    )
    project_manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='project_manager_boxes',
        help_text="The project manager who owns this Box"
    )
    rack = models.ForeignKey(
            Rack,
            on_delete=models.CASCADE,
            related_name='boxes'
    )
    box_label = models.CharField(max_length=50)
    row_count = models.PositiveSmallIntegerField(
        default=1,
        help_text="Number of rows in the box"
    )
    column_count = models.PositiveSmallIntegerField(
        default=1,
        help_text="Number of columns in the box"
    )
    notes = models.TextField()

    def save(self, *args, **kwargs):
        if not self.project_manager and self.project:
            self.project_manager = self.project.project_manager
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Box'
        verbose_name_plural = 'Boxes'

    @property
    def box_dimension_display(self):
        if not (self.row_count and self.column_count):
            return "N/A"
        return f"{self.row_count}x{self.column_count}"


class Sample(models.Model):
    """Model for biological samples"""
    id = models.CharField(
            primary_key=True,
            max_length=22,
            unique=True,
            default=generate_short_uuid,
            editable=False
    )
    project = models.ForeignKey(
            Project,
            on_delete=models.CASCADE,
            related_name='samples'
    )
    sample_id = models.CharField(
            max_length=50,
            unique=True,
            help_text="Unique sample identifier"
    )
    sample_type = models.CharField(max_length=50)
    country = models.CharField(max_length=100, null=True)
    volume = models.DecimalField(
            max_digits=10,
            decimal_places=2,
            help_text="Volume of Sample collected"
    )
    volume_unit = models.CharField(
        max_length=5,
        default='mL',
        choices=[('mL', 'mL'), ('µL', 'µL')]
    )
    concentration = models.DecimalField(
            max_digits=10,
            decimal_places=2,
            null=True,
            blank=True,
            help_text="Concentration of Sample"
    )
    concentration_unit = models.CharField(max_length=10, null=True, blank=True)
    collection_date = models.DateField()
    date_recorded = models.DateTimeField(auto_now_add=True)
    threshold_value = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField()

    class Meta:
        ordering = ['sample_id']
        verbose_name = 'Sample'
        verbose_name_plural = 'Samples'

    def __str__(self):
        return self.sample_id

    def clean(self):
        """Validate sample data"""
        super().clean()

        if self.collection_date and self.collection_date > timezone.now().date():
            raise ValidationError("Collection date cannot be in the future")

        if self.volume is not None and self.volume <= 0:
            raise ValidationError("Volume must be positive")

    @property
    def volume_display(self):
        if not (self.volume and self.volume_unit):
            return "N/A"
        return f"{self.volume}{self.volume_unit}"

    @property
    def concentration_display(self):
        if not (self.concentration and self.concentration_display):
            return "N/A"
        return f"{self.concentration}{self.concentration_display}"


class Sample_Locations(models.Model):
    """Model to track Sample Locations"""
    id = models.CharField(
            primary_key=True,
            max_length=22,
            unique=True,
            default=generate_short_uuid,
            editable=False
    )
    sample = models.ForeignKey(
            Sample,
            on_delete=models.PROTECT,
            related_name='sample_locations'
    )
    box = models.ForeignKey(
            Box,
            on_delete=models.PROTECT,
            related_name='sample_boxes'
    )
    well_id = models.CharField(
        max_length=10,
        blank=True,
        help_text="Well position (e.g., A1, B2)"
    )
    moved_in_at = models.DateField()
    moved_out_at = models.DateField(null=True, blank=True)


class TrashBaseModel(models.Model):
    """Abstract base model for trash/archive items"""
    deleted_at = models.DateTimeField(auto_now_add=True)
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deleted_%(class)s'
    )
    deletion_reason = models.CharField(
        max_length=255,
        blank=True,
        help_text="Reason for deletion"
    )

    class Meta:
        abstract = True
        ordering = ['-deleted_at']


class TrashConsumable(TrashBaseModel):
    """Archived consumables"""
    original_id = models.CharField(max_length=22)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='trash_consumables'
    )
    name = models.CharField(max_length=100)
    product_code = models.CharField(max_length=50, blank=True)
    items_per_pack = models.PositiveIntegerField()
    items_left_in_pack = models.PositiveIntegerField()
    pack_count = models.PositiveIntegerField()
    expiry_date = models.DateField(null=True, blank=True)
    date_recorded = models.DateField()
    threshold_value = models.PositiveIntegerField(null=True, blank=True)
    storage_location = models.CharField(max_length=100, blank=True)
    cold_storage = models.CharField(max_length=10)
    oem_temperature = models.IntegerField(null=True, blank=True)
    vendor = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = 'Trash Consumable'
        verbose_name_plural = 'Trash Consumables'

    def __str__(self):
        return f"[DELETED] {self.name}"


class TrashReagent(TrashBaseModel):
    """Archived reagents"""
    original_id = models.CharField(max_length=22)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='trash_reagents'
    )
    name = models.CharField(max_length=100)
    product_code = models.CharField(max_length=50, blank=True)
    items_per_pack = models.PositiveIntegerField()
    items_left_in_pack = models.PositiveIntegerField()
    pack_count = models.PositiveIntegerField()
    expiry_date = models.DateField(null=True, blank=True)
    date_recorded = models.DateField()
    cold_storage = models.CharField(max_length=10)
    oem_temperature = models.IntegerField(null=True, blank=True)
    temperature_unit = models.CharField(max_length=1, default='C')
    country_of_origin = models.CharField(max_length=100, blank=True)
    vendor = models.CharField(max_length=100, blank=True)
    threshold_value = models.PositiveIntegerField(null=True, blank=True)
    storage_location = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = 'Trash Reagent'
        verbose_name_plural = 'Trash Reagents'

    def __str__(self):
        return f"[DELETED] {self.name}"


class TrashEquipment(TrashBaseModel):
    """Archived equipment"""
    original_id = models.CharField(max_length=22)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='trash_equipment'
    )
    name = models.CharField(max_length=100)
    equip_id = models.CharField(max_length=100)
    serial_num = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=100)
    service_contract_start = models.DateField(null=True, blank=True)
    service_contract_end = models.DateField(null=True, blank=True)
    date_installed = models.DateField()
    source = models.CharField(max_length=100, blank=True, null=True)
    operating_temperature = models.IntegerField(null=True, blank=True)
    storage_location = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        verbose_name = 'Trash Equipment'
        verbose_name_plural = 'Trash Equipment'

    def __str__(self):
        return f"[DELETED] {self.name}"


class TrashSample(TrashBaseModel):
    """Archived samples"""
    original_id = models.CharField(max_length=22)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='trash_samples'
    )
    shelf = models.ForeignKey(
        Shelf,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='trash_samples'
    )
    rack = models.ForeignKey(
        Rack,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='trash_samples'
    )
    box = models.ForeignKey(
        Box,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='trash_samples'
    )
    sample_id = models.CharField(max_length=100)
    sample_type = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    country = models.CharField(max_length=100, blank=True)
    volume = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    well_id = models.CharField(max_length=100, blank=True, null=True)
    date_recorded = models.DateField()
    storage_location = models.CharField(max_length=100, blank=True, null=True)
    cold_storage_id = models.CharField(max_length=100, blank=True, null=True)
    storage_temperature = models.IntegerField(null=True, blank=True)
    threshold_value = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = 'Trash Sample'
        verbose_name_plural = 'Trash Samples'

    def __str__(self):
        return f"[DELETED] {self.sample_id}"
