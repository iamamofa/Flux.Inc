from django.contrib.auth.models import User
from django.db import models
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

static_img_path = os.path.join(settings.BASE_DIR, 'static')


class UserApplication(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    workplace = models.CharField(max_length=100)
    department = models.CharField(max_length=100)
    id_image = models.ImageField(upload_to='user_applications/')
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        try:
            # Resize and optimize image after saving
            img_path = self.id_image.path
            img = Image.open(img_path)

            output_size = (800, 600)
            img = img.resize(output_size, Image.LANCZOS)

            # Save with desired quality
            img.save(img_path, quality=70, optimize=True)
        except Exception as e:
            # Optional: log the error or raise it [Production]
            print(f"Image processing failed: {e}")

@receiver(post_save, sender=UserApplication)
def send_approval_email(sender, instance, created, **kwargs):
    if instance.is_approved:
        subject = 'Application Approved'
        recipient_list = [instance.email]

        # Generate prefilled form link
        # Replace with the unique token or identifier generated for the user
        token = uuid.uuid4().hex
        # Replace 'register_project_manager' with the URL name of your
        # registration view
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
                'settings.EMAIL_HOST_USER',
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
                    img = MIMEImage(open(file_path, 'rb').read())
                    img.add_header('Content-Id', f'<{filename}>')
                    msg.attach(img)
        try:
            msg.send()
        except Exception as e:
            print("Email failed to send:", e)


class Project(models.Model):
    name = models.CharField(max_length=255, unique=True)
    project_manager = models.ForeignKey(
            User,
            on_delete=models.CASCADE,
            related_name='managed_projects',
            null=True
    )
    project_editors = models.ManyToManyField(
            User,
            related_name='edited_projects',
            blank=True
    )
    project_members = models.ManyToManyField(
            User,
            related_name='project_membership',
            blank=True
    )

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    managed_projects = models.ManyToManyField(
            Project,
            related_name='related_projects',
            blank=True
    )
    # You can add additional fields to store user-related information

    def __str__(self):
        return self.user.username


class Log(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} by {self.user.username} on {self.project.name}"


class Consumable(models.Model):
    project = models.ForeignKey(Project, null=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=100, null=True)
    product_code = models.CharField(max_length=100, null=True)
    pack_size = models.PositiveIntegerField(null=True)
    pack_size_rem = models.PositiveIntegerField(null=True)
    quantity = models.PositiveIntegerField(null=True)
    expiry_date = models.DateField(null=True)
    date_recorded = models.DateField(auto_now_add=True)
    storage_location = models.CharField(max_length=100, null=True)
    threshold_value = models.PositiveIntegerField(null=True)

    def __str__(self):
        return self.name


class Reagent(models.Model):
    project = models.ForeignKey(Project, null=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=100, null=True)
    product_code = models.CharField(max_length=100, null=True)
    pack_size = models.PositiveIntegerField(null=True)
    pack_size_rem = models.PositiveIntegerField(null=True)
    quantity = models.PositiveIntegerField(null=True)
    expiry_date = models.DateField(null=True)
    date_recorded = models.DateField(auto_now_add=True)
    storage_location = models.CharField(max_length=100, null=True)
    threshold_value = models.PositiveIntegerField(null=True)

    def __str__(self):
        return self.name


class Equipment(models.Model):
    project = models.ForeignKey(Project, null=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=100, null=True)
    equip_id = models.CharField(max_length=100, null=True)
    serial_num = models.CharField(max_length=100, null=True)
    quantity = models.PositiveIntegerField(null=True)
    status = models.CharField(max_length=100, null=True)
    service_contract_start = models.DateField(null=True)
    service_contract_end = models.DateField(null=True)
    date_recorded = models.DateField(auto_now_add=True)
    donated_by = models.CharField(max_length=100, null=True)
    storage_location = models.CharField(max_length=100, null=True)

    def __str__(self):
        return self.name


class Shelf(models.Model):
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=100)
    project = models.ForeignKey(Project, null=True, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Box(models.Model):
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=100)
    shelf = models.ForeignKey(Shelf, null=True, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, null=True, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Sample(models.Model):
    project = models.ForeignKey(Project, null=True, on_delete=models.CASCADE)
    shelf = models.ForeignKey(Shelf, null=True, on_delete=models.CASCADE)
    box = models.ForeignKey(Box, null=True, on_delete=models.CASCADE)
    sample_id = models.CharField(max_length=100, null=True)
    sample_type = models.CharField(max_length=100, null=True)
    description = models.CharField(max_length=100, null=True)
    country = models.CharField(max_length=100, null=True)
    volume = models.PositiveIntegerField(null=True)
    well_id = models.CharField(max_length=100, null=True)
    date_recorded = models.DateField(auto_now_add=True, null=True)
    storage_location = models.CharField(max_length=100, null=True)
    threshold_value = models.PositiveIntegerField(null=True)

    def __str__(self):
        return self.sample_id


class TrashConsumable(models.Model):
    project = models.ForeignKey(Project, null=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    product_code = models.CharField(max_length=50)
    pack_size = models.PositiveIntegerField(null=True)
    pack_size_rem = models.PositiveIntegerField(null=True)
    quantity = models.PositiveIntegerField()
    expiry_date = models.DateField()
    date_recorded = models.DateField()
    threshold_value = models.PositiveIntegerField(null=True)
    storage_location = models.CharField(max_length=100, null=True)
    deleted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class TrashReagent(models.Model):
    project = models.ForeignKey(Project, null=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    product_code = models.CharField(max_length=50)
    pack_size = models.PositiveIntegerField(null=True)
    pack_size_rem = models.PositiveIntegerField(null=True)
    quantity = models.PositiveIntegerField()
    expiry_date = models.DateField()
    date_recorded = models.DateField()
    threshold_value = models.PositiveIntegerField(null=True)
    storage_location = models.CharField(max_length=100, null=True)
    deleted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class TrashEquipment(models.Model):
    project = models.ForeignKey(Project, null=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=100, null=True)
    equip_id = models.CharField(max_length=100, null=True)
    serial_num = models.CharField(max_length=100, null=True)
    quantity = models.PositiveIntegerField(null=True)
    status = models.CharField(max_length=100, null=True)
    service_contract_start = models.DateField(null=True)
    service_contract_end = models.DateField(null=True)
    date_recorded = models.DateField()
    donated_by = models.CharField(max_length=100, null=True)
    storage_location = models.CharField(max_length=100, null=True)

    def __str__(self):
        return self.name


class TrashSample(models.Model):
    project = models.ForeignKey(Project, null=True, on_delete=models.CASCADE)
    sample_id = models.CharField(max_length=100, null=True)
    sample_type = models.CharField(max_length=100, null=True)
    description = models.CharField(max_length=100, null=True)
    country = models.CharField(max_length=100, null=True)
    volume = models.PositiveIntegerField(null=True)
    well_id = models.CharField(max_length=100, null=True)
    date_recorded = models.DateField(null=True)
    storage_location = models.CharField(max_length=100, null=True)
    threshold_value = models.PositiveIntegerField(null=True)

    def __str__(self):
        return self.sample_id
